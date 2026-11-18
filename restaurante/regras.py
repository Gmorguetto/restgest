"""Regras de negócio do restaurante: a camada de lógica da aplicação.

As funções daqui não conhecem telas nem HTTP. Recebem a conexão com o
banco e o id do restaurante, validam as regras e gravam. As rotas
(gerente.py, garcom.py, cozinha.py, caixa.py) e os testes automáticos
usam as mesmas funções.

Regra de ouro do SaaS: toda consulta filtra por restaurante_id, para que
um restaurante nunca veja nem altere os dados de outro.

Escritas usam "with db:", que abre uma transação: se algo der errado no
meio, nada é gravado (rollback); se tudo der certo, grava tudo (commit).
"""
import sqlite3
from datetime import date, datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from .util import RegraViolada, agora, centavos_para_reais, chave_alfabetica, hoje, minutos_desde, plural

# Planos da assinatura. Os preços vêm da memória de cálculo em docs/precificacao.md:
# custos (rateio do custo fixo + suporte + taxa de cobrança) ÷ (1 − tributos − reserva − lucro).
PLANOS = {
    "teste": {
        "nome": "Teste grátis",
        "descricao": "14 dias com os limites do Básico",
        "preco_centavos": 0,
        "max_mesas": 10,
        "max_usuarios": 4,
        "suporte": "Suporte por e-mail e WhatsApp em dias úteis",
        "resposta": "até 1 dia útil",
    },
    "basico": {
        "nome": "Básico",
        "descricao": "Para lanchonetes e bares pequenos",
        "preco_centavos": 7900,
        "max_mesas": 10,
        "max_usuarios": 4,  # uma pessoa em cada perfil: gerente, garçom, cozinha e caixa
        "suporte": "30 min de orientação por mês",
        "resposta": "até 1 dia útil",
    },
    "profissional": {
        "nome": "Profissional",
        "descricao": "Para restaurantes de médio porte",
        "preco_centavos": 11900,
        "max_mesas": 40,
        "max_usuarios": 10,
        "suporte": "1 hora de orientação por mês",
        "resposta": "até 4 horas úteis",
    },
}

# Serviço opcional, cobrado uma vez por restaurante (8 h de trabalho; ver docs/precificacao.md)
IMPLANTACAO = {
    "nome": "Implantação assistida",
    "preco_centavos": 60000,
    "prazo": "até 5 dias úteis",
    "itens": [
        "Cadastro do cardápio, das mesas e da equipe",
        "Orientação da equipe no restaurante",
        "Acompanhamento do primeiro turno",
    ],
}

# O que a assinatura inclui e o que fica fora desta versão (o mesmo texto do PDF do trabalho)
INCLUSO_NA_MENSALIDADE = "Hospedagem, backup, atualizações e correções de erro"
FORA_DO_ESCOPO = [
    "aplicativo para Android ou iPhone (o sistema funciona no navegador)",
    "cardápio por QR code e pedido feito pelo cliente",
    "delivery e integração com iFood ou WhatsApp",
    "emissão de nota fiscal (NFC-e)",
    "impressora de cozinha e maquininha de cartão integradas",
    "controle de estoque",
    "várias unidades na mesma conta",
]
DIAS_DE_TESTE = 14

PERFIS = {"gerente": "Gerente", "garcom": "Garçom", "cozinha": "Cozinha", "caixa": "Caixa"}

STATUS_ITEM = {
    "novo": "Novo",
    "em_preparo": "Em preparo",
    "pronto": "Pronto",
    "entregue": "Entregue",
    "cancelado": "Cancelado",
}
# Caminho de um item: novo -> em_preparo -> pronto -> entregue (sem pular etapas)
TRANSICOES = {("novo", "em_preparo"), ("em_preparo", "pronto"), ("pronto", "entregue")}
NAO_ENTREGUES = ("novo", "em_preparo", "pronto")

FORMAS_PAGAMENTO = {"dinheiro": "Dinheiro", "cartao": "Cartão", "pix": "Pix"}

TAXA_SERVICO_MAXIMA = 20  # % — limite aceito no ajuste do gerente


def valor_da_taxa(consumo_centavos, percentual):
    """Taxa de serviço em centavos, arredondada para o centavo mais próximo.
    Ex.: 10% de R$ 72,95 = R$ 7,295 -> R$ 7,30."""
    return (consumo_centavos * percentual + 50) // 100


# ---------- Validações simples ----------

def _texto(valor, campo, maximo=80):
    valor = (valor or "").strip()
    if not valor:
        raise RegraViolada(f"Preencha o campo {campo}.")
    if len(valor) > maximo:
        raise RegraViolada(f"O campo {campo} aceita no máximo {maximo} caracteres.")
    return valor


def _email(valor):
    email = _texto(valor, "e-mail", 120).lower()
    usuario, _, dominio = email.partition("@")
    if not usuario or "." not in dominio or " " in email:
        raise RegraViolada("Informe um e-mail válido.")
    return email


def _senha(valor):
    if len(valor or "") < 6:
        raise RegraViolada("A senha precisa ter pelo menos 6 caracteres.")
    return valor


def _preco(centavos):
    if not isinstance(centavos, int) or centavos <= 0:
        raise RegraViolada("O preço precisa ser maior que zero.")
    return centavos


# ---------- Restaurante (cliente do SaaS) e plano ----------

def cadastrar_restaurante(db, nome_restaurante, nome_gerente, email, senha):
    """Cria um restaurante novo em teste grátis e o primeiro usuário (gerente)."""
    nome_restaurante = _texto(nome_restaurante, "nome do restaurante")
    teste_ate = (date.today() + timedelta(days=DIAS_DE_TESTE)).isoformat()
    with db:
        cursor = db.execute(
            "INSERT INTO restaurante (nome, plano, criado_em, teste_ate) VALUES (?, 'teste', ?, ?)",
            (nome_restaurante, agora(), teste_ate),
        )
        restaurante_id = cursor.lastrowid
        gerente_id = _inserir_usuario(db, restaurante_id, nome_gerente, email, senha, "gerente")
    return restaurante_id, gerente_id


def uso_do_plano(db, restaurante_id):
    """Plano atual, limites e quanto o restaurante já usa."""
    restaurante = db.execute("SELECT * FROM restaurante WHERE id = ?", (restaurante_id,)).fetchone()
    plano = PLANOS[restaurante["plano"]]
    mesas = db.execute(
        "SELECT COUNT(*) FROM mesa WHERE restaurante_id = ?", (restaurante_id,)
    ).fetchone()[0]
    usuarios = db.execute(
        "SELECT COUNT(*) FROM usuario WHERE restaurante_id = ? AND ativo = 1", (restaurante_id,)
    ).fetchone()[0]
    dias_de_teste = None
    if restaurante["plano"] == "teste" and restaurante["teste_ate"]:
        dias_de_teste = (date.fromisoformat(restaurante["teste_ate"]) - date.today()).days
    return {
        "restaurante_nome": restaurante["nome"],
        "plano": restaurante["plano"],
        "plano_nome": plano["nome"],
        "max_mesas": plano["max_mesas"],
        "max_usuarios": plano["max_usuarios"],
        "mesas": mesas,
        "usuarios": usuarios,
        "dias_de_teste": dias_de_teste,
        "taxa_servico": restaurante["taxa_servico"],
    }


def _verificar_assinatura(db, restaurante_id):
    uso = uso_do_plano(db, restaurante_id)
    if uso["dias_de_teste"] is not None and uso["dias_de_teste"] < 0:
        raise RegraViolada(
            "O período de teste terminou. O gerente precisa escolher um plano para continuar."
        )


def mudar_plano(db, restaurante_id, plano):
    """Troca de plano. No MVP a cobrança é simulada (sem gateway de pagamento)."""
    if plano not in PLANOS or plano == "teste":
        raise RegraViolada("Escolha um plano válido.")
    novo = PLANOS[plano]
    uso = uso_do_plano(db, restaurante_id)
    if uso["mesas"] > novo["max_mesas"]:
        raise RegraViolada(
            f"O plano {novo['nome']} permite até {novo['max_mesas']} mesas "
            f"e o restaurante tem {uso['mesas']}."
        )
    if uso["usuarios"] > novo["max_usuarios"]:
        raise RegraViolada(
            f"O plano {novo['nome']} permite até {novo['max_usuarios']} usuários ativos "
            f"e o restaurante tem {uso['usuarios']}. Desative alguém na Equipe antes de trocar."
        )
    with db:
        db.execute("UPDATE restaurante SET plano = ? WHERE id = ?", (plano, restaurante_id))


def configurar_taxa_servico(db, restaurante_id, percentual):
    """Define o % de taxa de serviço das próximas comandas (0 = não cobra).
    Comandas já abertas mantêm o % com que foram abertas."""
    if not isinstance(percentual, int) or not 0 <= percentual <= TAXA_SERVICO_MAXIMA:
        raise RegraViolada(f"A taxa de serviço deve ser de 0% a {TAXA_SERVICO_MAXIMA}%.")
    with db:
        db.execute("UPDATE restaurante SET taxa_servico = ? WHERE id = ?", (percentual, restaurante_id))


# ---------- Usuários e login ----------

def _inserir_usuario(db, restaurante_id, nome, email, senha, perfil):
    """Insere um usuário. Deve ser chamada dentro de uma transação (with db)."""
    nome = _texto(nome, "nome")
    email = _email(email)
    senha = _senha(senha)
    if perfil not in PERFIS:
        raise RegraViolada("Escolha um perfil válido.")
    if db.execute("SELECT 1 FROM usuario WHERE email = ?", (email,)).fetchone():
        raise RegraViolada("Este e-mail já está cadastrado.")
    cursor = db.execute(
        "INSERT INTO usuario (restaurante_id, nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?, ?)",
        (restaurante_id, nome, email, generate_password_hash(senha), perfil),
    )
    return cursor.lastrowid


def criar_usuario(db, restaurante_id, nome, email, senha, perfil):
    uso = uso_do_plano(db, restaurante_id)
    if uso["usuarios"] >= uso["max_usuarios"]:
        raise RegraViolada(
            f"O plano {uso['plano_nome']} permite até {uso['max_usuarios']} usuários ativos. "
            "Mude de plano para cadastrar mais."
        )
    with db:
        return _inserir_usuario(db, restaurante_id, nome, email, senha, perfil)


def alternar_usuario(db, restaurante_id, usuario_id, usuario_logado_id):
    """Ativa ou desativa o acesso de um usuário do mesmo restaurante."""
    if usuario_id == usuario_logado_id:
        raise RegraViolada("Você não pode desativar o seu próprio acesso.")
    usuario = db.execute(
        "SELECT ativo FROM usuario WHERE id = ? AND restaurante_id = ?", (usuario_id, restaurante_id)
    ).fetchone()
    if usuario is None:
        raise RegraViolada("Usuário não encontrado.")
    if not usuario["ativo"]:
        uso = uso_do_plano(db, restaurante_id)
        if uso["usuarios"] >= uso["max_usuarios"]:
            raise RegraViolada(f"O plano {uso['plano_nome']} já está no limite de usuários ativos.")
    with db:
        db.execute(
            "UPDATE usuario SET ativo = 1 - ativo WHERE id = ? AND restaurante_id = ?",
            (usuario_id, restaurante_id),
        )


def listar_usuarios(db, restaurante_id):
    return db.execute(
        "SELECT * FROM usuario WHERE restaurante_id = ? ORDER BY ativo DESC, nome",
        (restaurante_id,),
    ).fetchall()


def autenticar(db, email, senha):
    """Confere e-mail e senha. A senha digitada é comparada com o hash guardado."""
    usuario = db.execute(
        """SELECT u.*, r.ativo AS restaurante_ativo
           FROM usuario u JOIN restaurante r ON r.id = u.restaurante_id
           WHERE u.email = ?""",
        ((email or "").strip().lower(),),
    ).fetchone()
    if usuario is None or not check_password_hash(usuario["senha_hash"], senha or ""):
        raise RegraViolada("E-mail ou senha incorretos.")
    if not usuario["ativo"] or not usuario["restaurante_ativo"]:
        raise RegraViolada("Este acesso está desativado. Fale com o gerente do restaurante.")
    return usuario


def usuarios_de_demonstracao(db):
    """Usuários fictícios (e-mails terminados em .demo), listados na tela de login."""
    return db.execute(
        """SELECT u.email, u.nome, u.perfil, r.nome AS restaurante
           FROM usuario u JOIN restaurante r ON r.id = u.restaurante_id
           WHERE u.email LIKE '%.demo' AND u.ativo = 1
           ORDER BY r.id, u.id"""
    ).fetchall()


# ---------- Cardápio ----------

def criar_categoria(db, restaurante_id, nome):
    nome = _texto(nome, "nome da categoria", 40)
    try:
        with db:
            cursor = db.execute(
                "INSERT INTO categoria (restaurante_id, nome) VALUES (?, ?)", (restaurante_id, nome)
            )
    except sqlite3.IntegrityError:
        raise RegraViolada(f"Já existe a categoria {nome}.")
    return cursor.lastrowid


def criar_produto(db, restaurante_id, categoria_id, nome, preco_centavos):
    categoria = db.execute(
        "SELECT id FROM categoria WHERE id = ? AND restaurante_id = ?", (categoria_id, restaurante_id)
    ).fetchone()
    if categoria is None:
        raise RegraViolada("Escolha uma categoria.")
    nome = _texto(nome, "nome do produto")
    _preco(preco_centavos)
    with db:
        cursor = db.execute(
            "INSERT INTO produto (restaurante_id, categoria_id, nome, preco_centavos) VALUES (?, ?, ?, ?)",
            (restaurante_id, categoria_id, nome, preco_centavos),
        )
    return cursor.lastrowid


def editar_produto(db, restaurante_id, produto_id, nome, categoria_id, preco_centavos, ativo=True):
    """Muda nome, categoria, preço e disponibilidade de um produto.

    O novo preço vale para as próximas vendas: itens já lançados guardaram
    o preço do momento e não mudam.
    """
    produto = db.execute(
        "SELECT id FROM produto WHERE id = ? AND restaurante_id = ?", (produto_id, restaurante_id)
    ).fetchone()
    if produto is None:
        raise RegraViolada("Produto não encontrado.")
    categoria = db.execute(
        "SELECT id FROM categoria WHERE id = ? AND restaurante_id = ?", (categoria_id, restaurante_id)
    ).fetchone()
    if categoria is None:
        raise RegraViolada("Escolha uma categoria.")
    nome = _texto(nome, "nome do produto")
    _preco(preco_centavos)
    with db:
        db.execute(
            """UPDATE produto SET nome = ?, categoria_id = ?, preco_centavos = ?, ativo = ?
               WHERE id = ? AND restaurante_id = ?""",
            (nome, categoria_id, preco_centavos, 1 if ativo else 0, produto_id, restaurante_id),
        )
    return nome


def alternar_produto(db, restaurante_id, produto_id):
    """Ativa ou desativa um produto. Produto inativo não aparece para o garçom."""
    with db:
        cursor = db.execute(
            "UPDATE produto SET ativo = 1 - ativo WHERE id = ? AND restaurante_id = ?",
            (produto_id, restaurante_id),
        )
    if cursor.rowcount == 0:
        raise RegraViolada("Produto não encontrado.")


def cardapio(db, restaurante_id, so_ativos=False):
    """Categorias com seus produtos: [{'categoria': ..., 'produtos': [...]}, ...]"""
    categorias = db.execute(
        "SELECT * FROM categoria WHERE restaurante_id = ? ORDER BY id", (restaurante_id,)
    ).fetchall()
    filtro = " AND ativo = 1" if so_ativos else ""
    produtos = db.execute(
        "SELECT * FROM produto WHERE restaurante_id = ?" + filtro, (restaurante_id,)
    ).fetchall()
    produtos.sort(key=lambda produto: chave_alfabetica(produto["nome"]))
    grupos = []
    for categoria in categorias:
        itens = [p for p in produtos if p["categoria_id"] == categoria["id"]]
        if itens or not so_ativos:
            grupos.append({"categoria": categoria, "produtos": itens})
    return grupos


def contar_produtos(db, restaurante_id):
    return db.execute(
        "SELECT COUNT(*) FROM produto WHERE restaurante_id = ?", (restaurante_id,)
    ).fetchone()[0]


# ---------- Mesas ----------

def criar_mesa(db, restaurante_id, numero):
    if not isinstance(numero, int) or not 1 <= numero <= 999:
        raise RegraViolada("O número da mesa deve ser entre 1 e 999.")
    uso = uso_do_plano(db, restaurante_id)
    if uso["mesas"] >= uso["max_mesas"]:
        raise RegraViolada(
            f"O plano {uso['plano_nome']} permite até {uso['max_mesas']} mesas. "
            "Mude de plano para cadastrar mais."
        )
    try:
        with db:
            cursor = db.execute(
                "INSERT INTO mesa (restaurante_id, numero) VALUES (?, ?)", (restaurante_id, numero)
            )
    except sqlite3.IntegrityError:
        raise RegraViolada(f"A mesa {numero} já existe.")
    return cursor.lastrowid


def listar_mesas(db, restaurante_id):
    return db.execute(
        "SELECT * FROM mesa WHERE restaurante_id = ? ORDER BY numero", (restaurante_id,)
    ).fetchall()


def mesas_com_situacao(db, restaurante_id):
    """Mesas com a comanda aberta (se houver), o total e quantos itens estão prontos."""
    return db.execute(
        """SELECT s.*, s.consumo_centavos + (s.consumo_centavos * s.taxa_servico + 50) / 100 AS total_centavos
           FROM (SELECT m.id, m.numero, m.status, p.id AS pedido_id, p.aberto_em,
                        COALESCE(p.taxa_servico, 0) AS taxa_servico,
                        (SELECT COALESCE(SUM(i.quantidade * i.preco_unitario_centavos), 0)
                           FROM item_pedido i
                          WHERE i.pedido_id = p.id AND i.status != 'cancelado') AS consumo_centavos,
                        (SELECT COUNT(*) FROM item_pedido i
                          WHERE i.pedido_id = p.id AND i.status = 'pronto') AS prontos
                 FROM mesa m
                 LEFT JOIN pedido p ON p.mesa_id = m.id AND p.status = 'aberto'
                 WHERE m.restaurante_id = ?) s
           ORDER BY s.numero""",
        (restaurante_id,),
    ).fetchall()


# ---------- Comanda (pedido) e itens ----------

def abrir_pedido(db, restaurante_id, mesa_id, garcom_id):
    """Abre a comanda de uma mesa livre e marca a mesa como ocupada."""
    _verificar_assinatura(db, restaurante_id)
    mesa = db.execute(
        "SELECT * FROM mesa WHERE id = ? AND restaurante_id = ?", (mesa_id, restaurante_id)
    ).fetchone()
    if mesa is None:
        raise RegraViolada("Mesa não encontrada.")
    if mesa["status"] == "ocupada":
        raise RegraViolada(f"A mesa {mesa['numero']} já está ocupada.")
    taxa = db.execute(
        "SELECT taxa_servico FROM restaurante WHERE id = ?", (restaurante_id,)
    ).fetchone()["taxa_servico"]
    try:
        with db:
            cursor = db.execute(
                """INSERT INTO pedido (restaurante_id, mesa_id, garcom_id, aberto_em, taxa_servico)
                   VALUES (?, ?, ?, ?, ?)""",
                (restaurante_id, mesa_id, garcom_id, agora(), taxa),
            )
            db.execute("UPDATE mesa SET status = 'ocupada' WHERE id = ?", (mesa_id,))
    except sqlite3.IntegrityError:
        # O índice único do banco impediu uma segunda comanda aberta na mesma mesa
        # (dois garçons clicaram ao mesmo tempo).
        raise RegraViolada(f"A mesa {mesa['numero']} acabou de ser aberta por outra pessoa.")
    return cursor.lastrowid


def buscar_pedido(db, restaurante_id, pedido_id):
    """A comanda com o número da mesa e o nome do garçom, ou None se não for deste restaurante."""
    return db.execute(
        """SELECT p.*, m.numero AS mesa_numero, u.nome AS garcom_nome
           FROM pedido p
           JOIN mesa m ON m.id = p.mesa_id
           JOIN usuario u ON u.id = p.garcom_id
           WHERE p.id = ? AND p.restaurante_id = ?""",
        (pedido_id, restaurante_id),
    ).fetchone()


def _pedido_aberto(db, restaurante_id, pedido_id):
    pedido = buscar_pedido(db, restaurante_id, pedido_id)
    if pedido is None:
        raise RegraViolada("Comanda não encontrada.")
    if pedido["status"] != "aberto":
        raise RegraViolada("Esta comanda já foi encerrada.")
    return pedido


def adicionar_item(db, restaurante_id, pedido_id, produto_id, quantidade, observacao=""):
    """Lança um item na comanda. O preço do momento fica gravado no item."""
    _pedido_aberto(db, restaurante_id, pedido_id)
    produto = db.execute(
        "SELECT * FROM produto WHERE id = ? AND restaurante_id = ? AND ativo = 1",
        (produto_id, restaurante_id),
    ).fetchone()
    if produto is None:
        raise RegraViolada("Escolha um produto do cardápio.")
    if not isinstance(quantidade, int) or not 1 <= quantidade <= 50:
        raise RegraViolada("A quantidade deve ser entre 1 e 50.")
    observacao = (observacao or "").strip()
    if len(observacao) > 120:
        raise RegraViolada("A observação aceita no máximo 120 caracteres.")
    instante = agora()
    with db:
        cursor = db.execute(
            """INSERT INTO item_pedido
                 (pedido_id, produto_id, quantidade, preco_unitario_centavos, observacao,
                  criado_em, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pedido_id, produto["id"], quantidade, produto["preco_centavos"], observacao,
             instante, instante),
        )
    return cursor.lastrowid


def avancar_item(db, restaurante_id, item_id, de, para):
    """Muda o status de um item (ex.: de 'novo' para 'em_preparo').

    O UPDATE só acontece se o item ainda estiver no status 'de'. Se duas
    pessoas clicarem ao mesmo tempo, só a primeira consegue; a segunda
    recebe um aviso em vez de pular uma etapa.
    """
    if (de, para) not in TRANSICOES:
        raise RegraViolada("Mudança de status inválida.")
    with db:
        cursor = db.execute(
            """UPDATE item_pedido SET status = ?, atualizado_em = ?
               WHERE id = ? AND status = ?
                 AND pedido_id IN (SELECT id FROM pedido
                                   WHERE restaurante_id = ? AND status = 'aberto')""",
            (para, agora(), item_id, de, restaurante_id),
        )
    if cursor.rowcount == 0:
        raise RegraViolada("Este item mudou de situação antes da sua ação. Confira a lista atualizada.")


def avancar_itens_do_pedido(db, restaurante_id, pedido_id, de, para):
    """Avança de uma vez todos os itens de uma comanda que estão no status 'de'
    (ex.: "Iniciar todos" ou "Tudo pronto" na cozinha). Devolve quantos mudaram."""
    if (de, para) not in TRANSICOES:
        raise RegraViolada("Mudança de status inválida.")
    with db:
        cursor = db.execute(
            """UPDATE item_pedido SET status = ?, atualizado_em = ?
               WHERE pedido_id = ? AND status = ?
                 AND pedido_id IN (SELECT id FROM pedido
                                   WHERE id = ? AND restaurante_id = ? AND status = 'aberto')""",
            (para, agora(), pedido_id, de, pedido_id, restaurante_id),
        )
    if cursor.rowcount == 0:
        raise RegraViolada("Esta comanda mudou antes da sua ação. Confira a lista atualizada.")
    return cursor.rowcount


def comandas_da_cozinha(db, restaurante_id):
    """Itens da cozinha agrupados por mesa, separados em três colunas:
    {'novo': [...], 'em_preparo': [...], 'pronto': [...]}.

    Cada comanda traz a mesa, o garçom, os itens e há quanto tempo espera
    (desde o pedido mais antigo; nos prontos, desde que ficou pronto).
    """
    itens = db.execute(
        """SELECT i.*, pr.nome AS produto_nome, m.numero AS mesa_numero, u.nome AS garcom_nome
           FROM item_pedido i
           JOIN pedido p ON p.id = i.pedido_id
           JOIN produto pr ON pr.id = i.produto_id
           JOIN mesa m ON m.id = p.mesa_id
           JOIN usuario u ON u.id = p.garcom_id
           WHERE p.restaurante_id = ? AND p.status = 'aberto'
             AND i.status IN ('novo', 'em_preparo', 'pronto')
           ORDER BY i.criado_em, i.id""",
        (restaurante_id,),
    ).fetchall()
    colunas = {"novo": {}, "em_preparo": {}, "pronto": {}}
    for item in itens:
        comanda = colunas[item["status"]].setdefault(item["pedido_id"], {
            "pedido_id": item["pedido_id"],
            "mesa_numero": item["mesa_numero"],
            "garcom_nome": item["garcom_nome"],
            "desde": item["criado_em"],
            "pronto_desde": item["atualizado_em"],
            "itens": [],
        })
        comanda["itens"].append(item)
        comanda["pronto_desde"] = min(comanda["pronto_desde"], item["atualizado_em"])
    resultado = {}
    for status, comandas in colunas.items():
        lista = list(comandas.values())
        chave = "pronto_desde" if status == "pronto" else "desde"
        for comanda in lista:
            comanda["minutos"] = minutos_desde(comanda[chave])
        resultado[status] = sorted(lista, key=lambda c: c[chave])
    return resultado


def cancelar_item(db, restaurante_id, item_id):
    """Cancela um item que a cozinha ainda não começou a preparar."""
    with db:
        cursor = db.execute(
            """UPDATE item_pedido SET status = 'cancelado', atualizado_em = ?
               WHERE id = ? AND status = 'novo'
                 AND pedido_id IN (SELECT id FROM pedido
                                   WHERE restaurante_id = ? AND status = 'aberto')""",
            (agora(), item_id, restaurante_id),
        )
    if cursor.rowcount == 0:
        raise RegraViolada("Só é possível cancelar itens que a cozinha ainda não começou.")


def cancelar_pedido(db, restaurante_id, pedido_id):
    """Encerra uma comanda aberta por engano (sem itens) e libera a mesa."""
    pedido = _pedido_aberto(db, restaurante_id, pedido_id)
    ativos = db.execute(
        "SELECT COUNT(*) FROM item_pedido WHERE pedido_id = ? AND status != 'cancelado'",
        (pedido_id,),
    ).fetchone()[0]
    if ativos:
        raise RegraViolada("A comanda tem itens. Ela só pode ser encerrada no caixa.")
    with db:
        db.execute(
            "UPDATE pedido SET status = 'cancelado', fechado_em = ? WHERE id = ?",
            (agora(), pedido_id),
        )
        db.execute("UPDATE mesa SET status = 'livre' WHERE id = ?", (pedido["mesa_id"],))
    return pedido["mesa_numero"]


def itens_do_pedido(db, pedido_id):
    return db.execute(
        """SELECT i.*, pr.nome AS produto_nome,
                  i.quantidade * i.preco_unitario_centavos AS subtotal_centavos
           FROM item_pedido i JOIN produto pr ON pr.id = i.produto_id
           WHERE i.pedido_id = ?
           ORDER BY i.id""",
        (pedido_id,),
    ).fetchall()


def itens_por_status(db, restaurante_id, status):
    """Itens de comandas abertas em certos status, por ordem de chegada (fila da cozinha)."""
    marcadores = ", ".join("?" for _ in status)  # um "?" por status: nada do usuário entra no SQL
    return db.execute(
        f"""SELECT i.*, pr.nome AS produto_nome, m.numero AS mesa_numero
            FROM item_pedido i
            JOIN pedido p ON p.id = i.pedido_id
            JOIN produto pr ON pr.id = i.produto_id
            JOIN mesa m ON m.id = p.mesa_id
            WHERE p.restaurante_id = ? AND p.status = 'aberto' AND i.status IN ({marcadores})
            ORDER BY i.criado_em, i.id""",
        (restaurante_id, *status),
    ).fetchall()


# ---------- Conta e pagamento ----------

def resumo_conta(db, restaurante_id, pedido_id):
    """Tudo o que o caixa precisa: itens, total, quanto já foi pago e o que falta."""
    pedido = buscar_pedido(db, restaurante_id, pedido_id)
    if pedido is None:
        raise RegraViolada("Comanda não encontrada.")
    itens = itens_do_pedido(db, pedido_id)
    pagamentos = db.execute(
        "SELECT * FROM pagamento WHERE pedido_id = ? ORDER BY id", (pedido_id,)
    ).fetchall()
    consumo = sum(i["subtotal_centavos"] for i in itens if i["status"] != "cancelado")
    taxa = valor_da_taxa(consumo, pedido["taxa_servico"])
    total = consumo + taxa
    pago = sum(p["valor_centavos"] for p in pagamentos)
    return {
        "pedido": pedido,
        "itens": itens,
        "pagamentos": pagamentos,
        "consumo": consumo,
        "taxa_percentual": pedido["taxa_servico"],
        "taxa": taxa,
        "total": total,
        "pago": pago,
        "restante": max(total - pago, 0),
        "pendentes": sum(1 for i in itens if i["status"] in NAO_ENTREGUES),
        "ativos": sum(1 for i in itens if i["status"] != "cancelado"),
    }


def contas_abertas(db, restaurante_id):
    return db.execute(
        """SELECT c.*, c.consumo_centavos + (c.consumo_centavos * c.taxa_servico + 50) / 100 AS total_centavos
           FROM (
           SELECT p.id, p.aberto_em, p.taxa_servico, m.numero AS mesa_numero, u.nome AS garcom_nome,
                  COALESCE(SUM(CASE WHEN i.status != 'cancelado'
                                    THEN i.quantidade * i.preco_unitario_centavos END), 0) AS consumo_centavos,
                  COUNT(CASE WHEN i.status IN ('novo', 'em_preparo', 'pronto') THEN 1 END) AS pendentes,
                  COUNT(CASE WHEN i.status != 'cancelado' THEN 1 END) AS itens,
                  (SELECT COALESCE(SUM(pg.valor_centavos), 0)
                     FROM pagamento pg WHERE pg.pedido_id = p.id) AS pago_centavos
           FROM pedido p
           JOIN mesa m ON m.id = p.mesa_id
           JOIN usuario u ON u.id = p.garcom_id
           LEFT JOIN item_pedido i ON i.pedido_id = p.id
           WHERE p.restaurante_id = ? AND p.status = 'aberto'
           GROUP BY p.id
           ) c
           ORDER BY c.mesa_numero""",
        (restaurante_id,),
    ).fetchall()


def definir_taxa_servico(db, restaurante_id, pedido_id, cobrar):
    """Retira ou volta a incluir a taxa de serviço de uma comanda.

    A taxa é opcional para o cliente, então o caixa pode retirar. Só pode mudar
    antes do primeiro pagamento, para o valor já recebido não passar do total.
    """
    pedido = _pedido_aberto(db, restaurante_id, pedido_id)
    pago = db.execute(
        "SELECT COALESCE(SUM(valor_centavos), 0) FROM pagamento WHERE pedido_id = ?", (pedido_id,)
    ).fetchone()[0]
    if pago:
        raise RegraViolada("A taxa de serviço só pode ser alterada antes do primeiro pagamento.")
    percentual = 0
    if cobrar:
        percentual = db.execute(
            "SELECT taxa_servico FROM restaurante WHERE id = ?", (restaurante_id,)
        ).fetchone()["taxa_servico"]
        if percentual == 0:
            raise RegraViolada("O restaurante não cobra taxa de serviço. O gerente ativa em Ajustes.")
    with db:
        db.execute("UPDATE pedido SET taxa_servico = ? WHERE id = ?", (percentual, pedido["id"]))
    return percentual


def registrar_pagamento(db, restaurante_id, pedido_id, forma, valor_centavos):
    """Registra um pagamento. Quando a conta é quitada, fecha a comanda e libera a mesa.

    Regras:
    * a conta só é cobrada depois que todos os itens foram entregues;
    * cartão e Pix não podem passar do valor restante;
    * em dinheiro, o que passar do restante vira troco;
    * a conta pode ser dividida em vários pagamentos.
    """
    pedido = _pedido_aberto(db, restaurante_id, pedido_id)
    if forma not in FORMAS_PAGAMENTO:
        raise RegraViolada("Escolha a forma de pagamento.")
    conta = resumo_conta(db, restaurante_id, pedido_id)
    if conta["pendentes"]:
        raise RegraViolada(
            f"Ainda há {plural(conta['pendentes'], 'item não entregue', 'itens não entregues')}. "
            "A conta só pode ser cobrada depois da entrega."
        )
    if conta["consumo"] == 0:
        raise RegraViolada("A comanda não tem itens para cobrar.")
    restante = conta["restante"]
    troco = 0
    if valor_centavos > restante:
        if forma != "dinheiro":
            raise RegraViolada(
                f"O valor passa do que falta pagar ({centavos_para_reais(restante)}). "
                "Troco só existe em dinheiro."
            )
        troco = valor_centavos - restante
        valor_centavos = restante
    instante = agora()
    fechou = conta["pago"] + valor_centavos >= conta["total"]
    with db:
        db.execute(
            "INSERT INTO pagamento (pedido_id, forma, valor_centavos, pago_em) VALUES (?, ?, ?, ?)",
            (pedido_id, forma, valor_centavos, instante),
        )
        if fechou:
            db.execute(
                "UPDATE pedido SET status = 'fechado', fechado_em = ? WHERE id = ?",
                (instante, pedido_id),
            )
            db.execute("UPDATE mesa SET status = 'livre' WHERE id = ?", (pedido["mesa_id"],))
    return {
        "fechou": fechou,
        "troco": troco,
        "restante": restante - valor_centavos,
        "mesa_numero": pedido["mesa_numero"],
    }


# ---------- Painel do dia ----------

def vendas_por_hora(db, restaurante_id, dia=None):
    """Valor recebido em cada hora do dia, sem buracos, das primeiras horas até agora."""
    dia = dia or hoje()
    linhas = db.execute(
        """SELECT CAST(substr(pg.pago_em, 12, 2) AS INTEGER) AS hora,
                  SUM(pg.valor_centavos) AS valor, COUNT(DISTINCT pg.pedido_id) AS contas
           FROM pagamento pg JOIN pedido p ON p.id = pg.pedido_id
           WHERE p.restaurante_id = ? AND substr(pg.pago_em, 1, 10) = ?
           GROUP BY hora""",
        (restaurante_id, dia),
    ).fetchall()
    por_hora = {linha["hora"]: linha for linha in linhas}
    hora_atual = datetime.now().hour if dia == hoje() else 23
    inicio = max(0, min([*por_hora, hora_atual - 7]))
    fim = max([*por_hora, hora_atual])
    return [
        {
            "hora": hora,
            "valor": por_hora[hora]["valor"] if hora in por_hora else 0,
            "contas": por_hora[hora]["contas"] if hora in por_hora else 0,
            "atual": hora == hora_atual,
        }
        for hora in range(inicio, fim + 1)
    ]


def situacao_agora(db, restaurante_id, minutos_atraso=20):
    """O que está acontecendo agora e o que precisa de atenção do gerente."""
    contas = contas_abertas(db, restaurante_id)
    cozinha = comandas_da_cozinha(db, restaurante_id)
    mesas = db.execute(
        """SELECT COUNT(*) AS total, COALESCE(SUM(status = 'ocupada'), 0) AS ocupadas
           FROM mesa WHERE restaurante_id = ?""",
        (restaurante_id,),
    ).fetchone()

    alertas = []
    atrasadas = {}
    for comanda in cozinha["novo"] + cozinha["em_preparo"]:
        if comanda["minutos"] >= minutos_atraso:
            mesa = comanda["mesa_numero"]
            atrasadas[mesa] = max(atrasadas.get(mesa, 0), comanda["minutos"])
    for mesa, minutos in sorted(atrasadas.items(), key=lambda par: -par[1]):
        alertas.append({"tipo": "atrasado", "texto": f"Mesa {mesa} espera há {minutos} min na cozinha"})
    for comanda in cozinha["pronto"]:
        quantidade = len(comanda["itens"])
        alertas.append({
            "tipo": "pronto",
            "texto": f"Mesa {comanda['mesa_numero']}: {plural(quantidade, 'item pronto', 'itens prontos')} aguardando o garçom",
        })
    for conta in contas:
        if conta["itens"] and not conta["pendentes"]:
            alertas.append({
                "tipo": "cobrar",
                "texto": f"Mesa {conta['mesa_numero']} pronta para fechar a conta",
                "valor": conta["total_centavos"] - conta["pago_centavos"],
                "pedido_id": conta["id"],
            })

    return {
        "mesas_total": mesas["total"],
        "mesas_ocupadas": mesas["ocupadas"],
        "novos": sum(len(c["itens"]) for c in cozinha["novo"]),
        "em_preparo": sum(len(c["itens"]) for c in cozinha["em_preparo"]),
        "prontos": sum(len(c["itens"]) for c in cozinha["pronto"]),
        "em_aberto": sum(c["total_centavos"] - c["pago_centavos"] for c in contas),
        "contas_abertas": len(contas),
        "alertas": alertas,
    }


def resumo_do_dia(db, restaurante_id, dia=None):
    """Números do dia para o gerente. As datas são comparadas pelos 10 primeiros
    caracteres ('AAAA-MM-DD') do horário gravado."""
    dia = dia or hoje()
    recebido = db.execute(
        """SELECT COALESCE(SUM(pg.valor_centavos), 0)
           FROM pagamento pg JOIN pedido p ON p.id = pg.pedido_id
           WHERE p.restaurante_id = ? AND substr(pg.pago_em, 1, 10) = ?""",
        (restaurante_id, dia),
    ).fetchone()[0]
    # Ticket médio = valor das contas fechadas hoje / número dessas contas
    # (pagamentos parciais de mesas ainda abertas não entram).
    fechadas = db.execute(
        """SELECT COUNT(*) AS quantidade,
                  COALESCE(SUM((SELECT SUM(pg.valor_centavos) FROM pagamento pg
                                 WHERE pg.pedido_id = p.id)), 0) AS valor
           FROM pedido p
           WHERE p.restaurante_id = ? AND p.status = 'fechado' AND substr(p.fechado_em, 1, 10) = ?""",
        (restaurante_id, dia),
    ).fetchone()
    contas_fechadas = fechadas["quantidade"]
    mais_vendidos = db.execute(
        """SELECT pr.nome, SUM(i.quantidade) AS quantidade,
                  SUM(i.quantidade * i.preco_unitario_centavos) AS receita
           FROM item_pedido i
           JOIN pedido p ON p.id = i.pedido_id
           JOIN produto pr ON pr.id = i.produto_id
           WHERE p.restaurante_id = ? AND p.status = 'fechado'
             AND substr(p.fechado_em, 1, 10) = ? AND i.status = 'entregue'
           GROUP BY pr.id
           ORDER BY quantidade DESC, receita DESC
           LIMIT 5""",
        (restaurante_id, dia),
    ).fetchall()
    por_forma = db.execute(
        """SELECT pg.forma, SUM(pg.valor_centavos) AS valor
           FROM pagamento pg JOIN pedido p ON p.id = pg.pedido_id
           WHERE p.restaurante_id = ? AND substr(pg.pago_em, 1, 10) = ?
           GROUP BY pg.forma
           ORDER BY valor DESC""",
        (restaurante_id, dia),
    ).fetchall()
    mesas = db.execute(
        """SELECT COUNT(*) AS total, COALESCE(SUM(status = 'ocupada'), 0) AS ocupadas
           FROM mesa WHERE restaurante_id = ?""",
        (restaurante_id,),
    ).fetchone()
    na_cozinha = len(itens_por_status(db, restaurante_id, ("novo", "em_preparo")))
    # Contas fechadas hoje por garçom (quem abriu a mesa): quanto vendeu, sem a taxa, e a taxa
    # de serviço de cada um (base para dividir a gorjeta). O primeiro é o que mais vendeu.
    por_garcom = db.execute(
        """SELECT u.nome, COUNT(*) AS contas, SUM(x.consumo) AS vendido,
                  SUM(x.consumo) / COUNT(*) AS ticket,
                  SUM((x.consumo * x.taxa_servico + 50) / 100) AS taxa
           FROM (SELECT p.garcom_id, p.taxa_servico,
                        (SELECT COALESCE(SUM(i.quantidade * i.preco_unitario_centavos), 0)
                           FROM item_pedido i
                          WHERE i.pedido_id = p.id AND i.status != 'cancelado') AS consumo
                 FROM pedido p
                 WHERE p.restaurante_id = ? AND p.status = 'fechado'
                   AND substr(p.fechado_em, 1, 10) = ?) x
           JOIN usuario u ON u.id = x.garcom_id
           GROUP BY u.id
           ORDER BY vendido DESC, contas DESC, u.nome""",
        (restaurante_id, dia),
    ).fetchall()
    return {
        "dia": dia,
        "recebido": recebido,
        "contas_fechadas": contas_fechadas,
        "ticket_medio": fechadas["valor"] // contas_fechadas if contas_fechadas else 0,
        "mais_vendidos": mais_vendidos,
        "por_forma": [
            {"forma": linha["forma"], "nome": FORMAS_PAGAMENTO[linha["forma"]], "valor": linha["valor"]}
            for linha in por_forma
        ],
        "mesas_total": mesas["total"],
        "mesas_ocupadas": mesas["ocupadas"],
        "na_cozinha": na_cozinha,
        "taxa_servico": sum(linha["taxa"] for linha in por_garcom),
        "por_garcom": por_garcom,
    }
