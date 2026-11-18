"""Testes das regras de negócio (regras.py e util.py), sem passar pelas telas."""
from datetime import date, timedelta

import pytest
from conftest import LANCHONETE, SABOR, SENHA, id_mesa, id_produto, id_restaurante, id_usuario

from restaurante import regras
from restaurante.util import (
    RegraViolada,
    centavos_para_reais,
    centavos_para_reais_curto,
    escala_bonita,
    figura_categoria,
    reais_para_centavos,
    urgencia,
)


# ---------- Dinheiro ----------

@pytest.mark.parametrize(
    "digitado, centavos",
    [("12,50", 1250), ("12.50", 1250), ("R$ 1.234,56", 123456), ("7", 700), (" 0,05 ", 5)],
)
def test_converte_reais_para_centavos(digitado, centavos):
    assert reais_para_centavos(digitado) == centavos


@pytest.mark.parametrize("digitado", ["", "abc", "0", "-3", "1,234", "nan", "inf"])
def test_recusa_valores_invalidos(digitado):
    with pytest.raises(RegraViolada):
        reais_para_centavos(digitado)


def test_cardapio_em_ordem_alfabetica_com_acentos(db):
    grupos = regras.cardapio(db, id_restaurante(db, SABOR))
    bebidas = next(g for g in grupos if g["categoria"]["nome"] == "Bebidas")
    assert [p["nome"] for p in bebidas["produtos"]][:2] == ["Água mineral", "Cerveja long neck"]


def test_formata_centavos_em_reais():
    assert centavos_para_reais(123456) == "R$ 1.234,56"
    assert centavos_para_reais(5) == "R$ 0,05"


# ---------- Comanda ----------

def _comanda(db, numero_mesa=5):
    """Abre uma comanda no Sabor da Casa e devolve (restaurante, pedido)."""
    rid = id_restaurante(db, SABOR)
    garcom = id_usuario(db, "garcom@sabordacasa.demo")
    pedido = regras.abrir_pedido(db, rid, id_mesa(db, rid, numero_mesa), garcom)
    return rid, pedido


def _lancar_e_entregar(db, rid, pedido, produto, quantidade=1):
    item = regras.adicionar_item(db, rid, pedido, id_produto(db, rid, produto), quantidade)
    for de, para in (("novo", "em_preparo"), ("em_preparo", "pronto"), ("pronto", "entregue")):
        regras.avancar_item(db, rid, item, de, para)
    return item


def test_nao_abre_duas_comandas_na_mesma_mesa(db):
    rid, _ = _comanda(db)
    with pytest.raises(RegraViolada, match="já está ocupada"):
        _comanda(db)


def test_indice_do_banco_impede_comanda_dupla_mesmo_com_corrida(db):
    """Simula dois garçons abrindo a mesa ao mesmo tempo: o segundo leu a mesa como livre."""
    rid, _ = _comanda(db)
    db.execute("UPDATE mesa SET status = 'livre' WHERE id = ?", (id_mesa(db, rid, 5),))
    db.commit()
    with pytest.raises(RegraViolada, match="acabou de ser aberta"):
        _comanda(db)


def test_nao_lanca_produto_de_outro_restaurante(db):
    rid, pedido = _comanda(db)
    x_burger = id_produto(db, id_restaurante(db, LANCHONETE), "X-Burger")
    with pytest.raises(RegraViolada, match="Escolha um produto"):
        regras.adicionar_item(db, rid, pedido, x_burger, 1)


def _categoria(db, restaurante_id, nome):
    return db.execute(
        "SELECT id FROM categoria WHERE restaurante_id = ? AND nome = ?", (restaurante_id, nome)
    ).fetchone()["id"]


def test_preco_fica_registrado_no_momento_da_venda(db):
    rid, pedido = _comanda(db)
    feijoada = id_produto(db, rid, "Feijoada completa")
    regras.adicionar_item(db, rid, pedido, feijoada, 2)
    regras.editar_produto(db, rid, feijoada, "Feijoada completa", _categoria(db, rid, "Pratos"), 9900)
    assert regras.resumo_conta(db, rid, pedido)["consumo"] == 2 * 4290


def test_edita_nome_categoria_preco_e_disponibilidade(db):
    rid = id_restaurante(db, SABOR)
    suco = id_produto(db, rid, "Suco natural")
    regras.editar_produto(db, rid, suco, "  Suco de laranja  ", _categoria(db, rid, "Sobremesas"), 1050, ativo=False)
    produto = db.execute("SELECT * FROM produto WHERE id = ?", (suco,)).fetchone()
    assert (produto["nome"], produto["preco_centavos"], produto["ativo"]) == ("Suco de laranja", 1050, 0)
    assert produto["categoria_id"] == _categoria(db, rid, "Sobremesas")
    # Indisponível: some da lista do garçom
    nomes = [p["nome"] for g in regras.cardapio(db, rid, so_ativos=True) for p in g["produtos"]]
    assert "Suco de laranja" not in nomes


def test_nao_edita_produto_nem_usa_categoria_de_outro_restaurante(db):
    sabor, lanchonete = id_restaurante(db, SABOR), id_restaurante(db, LANCHONETE)
    x_burger = id_produto(db, lanchonete, "X-Burger")
    with pytest.raises(RegraViolada, match="Produto não encontrado"):
        regras.editar_produto(db, sabor, x_burger, "Hackeado", _categoria(db, sabor, "Pratos"), 100)
    pudim = id_produto(db, sabor, "Pudim de leite")
    with pytest.raises(RegraViolada, match="Escolha uma categoria"):
        regras.editar_produto(db, sabor, pudim, "Pudim", _categoria(db, lanchonete, "Lanches"), 1200)
    with pytest.raises(RegraViolada, match="Preencha o campo nome"):
        regras.editar_produto(db, sabor, pudim, "   ", _categoria(db, sabor, "Sobremesas"), 1200)


def test_item_segue_a_ordem_dos_status(db):
    rid, pedido = _comanda(db)
    item = regras.adicionar_item(db, rid, pedido, id_produto(db, rid, "Pudim de leite"), 1)
    with pytest.raises(RegraViolada, match="inválida"):
        regras.avancar_item(db, rid, item, "novo", "entregue")
    regras.avancar_item(db, rid, item, "novo", "em_preparo")
    # Segundo clique no mesmo botão (ou outra pessoa ao mesmo tempo): não pula etapa
    with pytest.raises(RegraViolada, match="mudou de situação"):
        regras.avancar_item(db, rid, item, "novo", "em_preparo")


def test_so_cancela_item_que_a_cozinha_nao_comecou(db):
    rid, pedido = _comanda(db)
    suco = id_produto(db, rid, "Suco natural")
    primeiro = regras.adicionar_item(db, rid, pedido, suco, 1)
    segundo = regras.adicionar_item(db, rid, pedido, suco, 1)
    regras.cancelar_item(db, rid, primeiro)
    regras.avancar_item(db, rid, segundo, "novo", "em_preparo")
    with pytest.raises(RegraViolada):
        regras.cancelar_item(db, rid, segundo)
    assert regras.resumo_conta(db, rid, pedido)["consumo"] == 900


# ---------- Pagamento ----------

def test_conta_so_fecha_depois_da_entrega(db):
    rid, pedido = _comanda(db)
    regras.adicionar_item(db, rid, pedido, id_produto(db, rid, "Moqueca de peixe"), 1)
    with pytest.raises(RegraViolada, match="não entregue"):
        regras.registrar_pagamento(db, rid, pedido, "pix", 5400)


def test_dinheiro_calcula_troco_e_libera_a_mesa(db):
    rid, pedido = _comanda(db)
    _lancar_e_entregar(db, rid, pedido, "Moqueca de peixe")  # 54,00 + 10% = 59,40
    resultado = regras.registrar_pagamento(db, rid, pedido, "dinheiro", 6000)
    assert resultado == {"fechou": True, "troco": 60, "restante": 0, "mesa_numero": 5}
    mesa = db.execute("SELECT status FROM mesa WHERE id = ?", (id_mesa(db, rid, 5),)).fetchone()
    assert mesa["status"] == "livre"


def test_cartao_nao_aceita_valor_acima_do_restante(db):
    rid, pedido = _comanda(db)
    _lancar_e_entregar(db, rid, pedido, "Moqueca de peixe")
    with pytest.raises(RegraViolada, match="Troco só existe em dinheiro"):
        regras.registrar_pagamento(db, rid, pedido, "cartao", 6000)


def test_conta_dividida_fecha_no_ultimo_pagamento(db):
    rid, pedido = _comanda(db)
    _lancar_e_entregar(db, rid, pedido, "Feijoada completa", 2)  # 85,80 + 10% = 94,38
    primeiro = regras.registrar_pagamento(db, rid, pedido, "pix", 4719)
    assert primeiro["fechou"] is False and primeiro["restante"] == 4719
    segundo = regras.registrar_pagamento(db, rid, pedido, "cartao", 4719)
    assert segundo["fechou"] is True
    with pytest.raises(RegraViolada, match="encerrada"):
        regras.registrar_pagamento(db, rid, pedido, "pix", 100)


# ---------- SaaS: planos e isolamento ----------

def test_limite_de_mesas_do_plano(db):
    rid = id_restaurante(db, LANCHONETE)  # plano Básico: até 10 mesas, já tem 6
    for numero in range(7, 11):
        regras.criar_mesa(db, rid, numero)
    with pytest.raises(RegraViolada, match="até 10 mesas"):
        regras.criar_mesa(db, rid, 11)


def test_limite_de_usuarios_do_plano(db):
    rid = id_restaurante(db, LANCHONETE)  # plano Básico: até 4 usuários (um por perfil), já tem 3
    regras.criar_usuario(db, rid, "Helena", "caixa@lanchonetedobairro.demo", SENHA, "caixa")
    with pytest.raises(RegraViolada, match="até 4 usuários"):
        regras.criar_usuario(db, rid, "Igor", "garcom2@lanchonetedobairro.demo", SENHA, "garcom")


def test_planos_seguem_a_memoria_de_calculo():
    # docs/precificacao.md: Básico R$ 79 e Profissional R$ 119; o teste grátis tem os limites do Básico
    assert regras.PLANOS["basico"]["preco_centavos"] == 7900
    assert regras.PLANOS["profissional"]["preco_centavos"] == 11900
    assert regras.IMPLANTACAO["preco_centavos"] == 60000
    assert regras.PLANOS["basico"]["max_usuarios"] == len(regras.PERFIS)  # uma pessoa em cada perfil
    for limite in ("max_mesas", "max_usuarios"):
        assert regras.PLANOS["teste"][limite] == regras.PLANOS["basico"][limite]


def test_nao_reduz_plano_abaixo_do_que_ja_usa(db):
    rid = id_restaurante(db, SABOR)  # 12 mesas
    with pytest.raises(RegraViolada, match="até 10 mesas"):
        regras.mudar_plano(db, rid, "basico")


def test_teste_gratis_vencido_bloqueia_novas_comandas(db):
    rid, gerente = regras.cadastrar_restaurante(db, "Bar Novo", "Íris", "iris@barnovo.com", SENHA)
    mesa = regras.criar_mesa(db, rid, 1)
    ontem = (date.today() - timedelta(days=1)).isoformat()
    db.execute("UPDATE restaurante SET teste_ate = ? WHERE id = ?", (ontem, rid))
    db.commit()
    with pytest.raises(RegraViolada, match="período de teste terminou"):
        regras.abrir_pedido(db, rid, mesa, gerente)


def test_email_repetido_nao_cria_restaurante(db):
    total_antes = db.execute("SELECT COUNT(*) FROM restaurante").fetchone()[0]
    with pytest.raises(RegraViolada, match="já está cadastrado"):
        regras.cadastrar_restaurante(db, "Outro", "Ana", "gerente@sabordacasa.demo", SENHA)
    # A transação desfez também o restaurante que tinha sido inserido
    assert db.execute("SELECT COUNT(*) FROM restaurante").fetchone()[0] == total_antes


def test_senha_e_guardada_como_hash(db):
    linha = db.execute("SELECT senha_hash FROM usuario WHERE email = 'caixa@sabordacasa.demo'").fetchone()
    assert SENHA not in linha["senha_hash"]
    assert linha["senha_hash"].startswith(("scrypt:", "pbkdf2:"))


# ---------- Painel ----------

def test_resumo_do_dia_com_os_dados_de_demonstracao(db):
    resumo = regras.resumo_do_dia(db, id_restaurante(db, SABOR))
    # 3 contas com 10%: 115,80 + 11,58 (Pix) + 79,40 + 7,94 (cartão) + 41,00 + 4,10 (dinheiro)
    assert resumo["recebido"] == 25982
    assert resumo["contas_fechadas"] == 3
    assert resumo["ticket_medio"] == 25982 // 3
    assert resumo["taxa_servico"] == 1158 + 794 + 410
    # Bruno atendeu as mesas 3 e 1; Júlia, a mesa 7. O primeiro da lista é quem mais vendeu.
    assert [(g["nome"], g["contas"], g["vendido"], g["taxa"]) for g in resumo["por_garcom"]] == [
        ("Bruno Lima", 2, 15680, 1568),
        ("Júlia Martins", 1, 7940, 794),
    ]
    assert resumo["por_garcom"][0]["ticket"] == 7840
    assert resumo["mais_vendidos"][0]["nome"] == "Feijoada completa"
    assert resumo["mesas_ocupadas"] == 2
    assert resumo["na_cozinha"] == 2


# ---------- Taxa de serviço (10%) ----------

def test_taxa_arredonda_para_o_centavo_mais_proximo():
    assert regras.valor_da_taxa(7290, 10) == 729
    assert regras.valor_da_taxa(7295, 10) == 730  # 729,5 centavos -> 730
    assert regras.valor_da_taxa(7290, 0) == 0


def test_taxa_de_servico_entra_no_total(db):
    rid, pedido = _comanda(db)
    _lancar_e_entregar(db, rid, pedido, "Moqueca de peixe")
    conta = regras.resumo_conta(db, rid, pedido)
    assert (conta["consumo"], conta["taxa_percentual"], conta["taxa"], conta["total"]) == (5400, 10, 540, 5940)


def test_caixa_retira_e_inclui_a_taxa_so_antes_de_receber(db):
    rid, pedido = _comanda(db)
    _lancar_e_entregar(db, rid, pedido, "Moqueca de peixe")
    regras.definir_taxa_servico(db, rid, pedido, cobrar=False)
    assert regras.resumo_conta(db, rid, pedido)["total"] == 5400
    regras.definir_taxa_servico(db, rid, pedido, cobrar=True)
    assert regras.resumo_conta(db, rid, pedido)["total"] == 5940
    regras.registrar_pagamento(db, rid, pedido, "pix", 1000)
    with pytest.raises(RegraViolada, match="antes do primeiro pagamento"):
        regras.definir_taxa_servico(db, rid, pedido, cobrar=False)


def test_restaurante_sem_taxa_nao_cobra(db):
    rid = id_restaurante(db, LANCHONETE)  # a Lanchonete não cobra 10%
    garcom = id_usuario(db, "garcom@lanchonetedobairro.demo")
    pedido = regras.abrir_pedido(db, rid, id_mesa(db, rid, 1), garcom)
    regras.adicionar_item(db, rid, pedido, id_produto(db, rid, "X-Burger"), 1)
    conta = regras.resumo_conta(db, rid, pedido)
    assert (conta["taxa_percentual"], conta["total"]) == (0, 2200)
    with pytest.raises(RegraViolada, match="não cobra taxa"):
        regras.definir_taxa_servico(db, rid, pedido, cobrar=True)


def test_novo_percentual_vale_para_as_proximas_comandas(db):
    rid, antiga = _comanda(db, numero_mesa=5)
    regras.configurar_taxa_servico(db, rid, 12)
    _, nova = _comanda(db, numero_mesa=6)
    assert regras.resumo_conta(db, rid, antiga)["taxa_percentual"] == 10
    assert regras.resumo_conta(db, rid, nova)["taxa_percentual"] == 12
    for invalido in (21, -1, None):
        with pytest.raises(RegraViolada, match="de 0% a 20%"):
            regras.configurar_taxa_servico(db, rid, invalido)


def test_atualizacao_acrescenta_a_taxa_em_banco_antigo(tmp_path):
    """Um banco criado antes da taxa de serviço ganha as colunas sem perder dados."""
    import sqlite3
    from restaurante import create_app
    from restaurante.db import atualizar_banco, get_db

    caminho = tmp_path / "antigo.db"
    antigo = sqlite3.connect(caminho)
    antigo.executescript("""
        CREATE TABLE restaurante (id INTEGER PRIMARY KEY, nome TEXT, plano TEXT, ativo INTEGER,
                                  criado_em TEXT, teste_ate TEXT);
        CREATE TABLE pedido (id INTEGER PRIMARY KEY, restaurante_id INTEGER, mesa_id INTEGER,
                             garcom_id INTEGER, status TEXT, aberto_em TEXT, fechado_em TEXT);
        INSERT INTO restaurante VALUES (1, 'Antigo', 'basico', 1, '2026-11-01 10:00:00', NULL);
        INSERT INTO pedido VALUES (1, 1, 1, 1, 'fechado', '2026-11-01 12:00:00', '2026-11-01 13:00:00');
        INSERT INTO pedido VALUES (2, 1, 2, 1, 'aberto', '2026-11-17 19:00:00', NULL);
    """)
    antigo.close()
    app = create_app({"TESTING": True, "DATABASE": str(caminho), "SECRET_KEY": "x" * 16})
    with app.app_context():
        atualizar_banco()  # rodar de novo não pode quebrar
        db = get_db()
        assert db.execute("SELECT nome, taxa_servico FROM restaurante").fetchone()[:] == ("Antigo", 10)
        taxas = [linha[0] for linha in db.execute("SELECT taxa_servico FROM pedido ORDER BY id")]
        assert taxas == [0, 10]  # a conta fechada fica como foi paga; a aberta passa a ter 10%


# ---------- Cozinha em comandas ----------

def _pedido_da_mesa(db, rid, numero):
    return db.execute(
        "SELECT p.id FROM pedido p JOIN mesa m ON m.id = p.mesa_id "
        "WHERE p.restaurante_id = ? AND m.numero = ? AND p.status = 'aberto'",
        (rid, numero),
    ).fetchone()["id"]


def test_cozinha_agrupa_os_itens_por_comanda(db):
    rid = id_restaurante(db, SABOR)
    colunas = regras.comandas_da_cozinha(db, rid)
    # Mesa 2: 2 sucos esperando e a moqueca no fogo; mesa 4: sobremesa pronta
    assert [(c["mesa_numero"], [i["produto_nome"] for i in c["itens"]]) for c in colunas["novo"]] == [(2, ["Suco natural"])]
    assert [c["mesa_numero"] for c in colunas["em_preparo"]] == [2]
    assert [c["mesa_numero"] for c in colunas["pronto"]] == [4]
    assert colunas["novo"][0]["garcom_nome"] == "Bruno Lima"
    assert 11 <= colunas["novo"][0]["minutos"] <= 13
    # Item entregue (a feijoada da mesa 4) não aparece mais na cozinha
    todos = [i["produto_nome"] for coluna in colunas.values() for c in coluna for i in c["itens"]]
    assert "Feijoada completa" not in todos


def test_cozinha_ordena_da_comanda_mais_antiga_para_a_mais_nova(db):
    rid, pedido = _comanda(db, 6)
    regras.adicionar_item(db, rid, pedido, id_produto(db, rid, "Pudim de leite"), 1)
    novos = regras.comandas_da_cozinha(db, rid)["novo"]
    assert [c["mesa_numero"] for c in novos] == [2, 6]


def test_cozinha_avanca_a_comanda_inteira_de_uma_vez(db):
    rid, pedido = _comanda(db)
    for produto in ("Feijoada completa", "Suco natural"):
        regras.adicionar_item(db, rid, pedido, id_produto(db, rid, produto), 1)
    assert regras.avancar_itens_do_pedido(db, rid, pedido, "novo", "em_preparo") == 2
    assert {i["status"] for i in regras.itens_do_pedido(db, pedido)} == {"em_preparo"}
    # Clique repetido (ou de outra tela) não muda nada e avisa
    with pytest.raises(RegraViolada, match="comanda mudou"):
        regras.avancar_itens_do_pedido(db, rid, pedido, "novo", "em_preparo")
    with pytest.raises(RegraViolada, match="inválida"):
        regras.avancar_itens_do_pedido(db, rid, pedido, "novo", "entregue")


def test_cozinha_nao_avanca_comanda_de_outro_restaurante(db):
    rid, pedido = _comanda(db)
    regras.adicionar_item(db, rid, pedido, id_produto(db, rid, "Pudim de leite"), 1)
    with pytest.raises(RegraViolada):
        regras.avancar_itens_do_pedido(db, id_restaurante(db, LANCHONETE), pedido, "novo", "em_preparo")


# ---------- Painel ----------

def test_vendas_por_hora_somam_o_recebido_e_nao_tem_buracos(db):
    rid = id_restaurante(db, SABOR)
    horas = regras.vendas_por_hora(db, rid)
    assert sum(h["valor"] for h in horas) == regras.resumo_do_dia(db, rid)["recebido"]
    assert sum(h["contas"] for h in horas) >= 3
    assert [h["hora"] for h in horas] == list(range(horas[0]["hora"], horas[-1]["hora"] + 1))
    assert horas[-1]["atual"] and sum(h["atual"] for h in horas) == 1


def test_situacao_agora_mostra_mesas_cozinha_e_avisos(db):
    rid = id_restaurante(db, SABOR)
    agora = regras.situacao_agora(db, rid)
    assert (agora["mesas_ocupadas"], agora["mesas_total"]) == (2, 12)
    assert (agora["novos"], agora["em_preparo"], agora["prontos"]) == (1, 1, 1)
    assert agora["contas_abertas"] == 2
    tipos = [a["tipo"] for a in agora["alertas"]]
    assert tipos == ["pronto"] and "Mesa 4" in agora["alertas"][0]["texto"]

    # Com limite menor, a mesa 2 (12 min) passa a contar como atrasada
    atrasos = [a for a in regras.situacao_agora(db, rid, minutos_atraso=10)["alertas"] if a["tipo"] == "atrasado"]
    assert len(atrasos) == 1 and "Mesa 2" in atrasos[0]["texto"]

    # Entregue a sobremesa, a mesa 4 fica pronta para o caixa cobrar
    pedido = _pedido_da_mesa(db, rid, 4)
    item = next(i["id"] for i in regras.itens_do_pedido(db, pedido) if i["status"] == "pronto")
    regras.avancar_item(db, rid, item, "pronto", "entregue")
    cobrar = [a for a in regras.situacao_agora(db, rid)["alertas"] if a["tipo"] == "cobrar"]
    assert [a["pedido_id"] for a in cobrar] == [pedido]
    assert cobrar[0]["valor"] == regras.resumo_conta(db, rid, pedido)["restante"]


def test_restaurante_sem_movimento_tem_painel_vazio(db):
    rid = id_restaurante(db, LANCHONETE)
    agora = regras.situacao_agora(db, rid)
    assert agora["alertas"] == [] and agora["mesas_ocupadas"] == 0 and agora["em_aberto"] == 0
    assert all(h["valor"] == 0 for h in regras.vendas_por_hora(db, rid))


@pytest.mark.parametrize(
    "maximo, topo, marcas",
    [
        (13000, 15000, [0, 5000, 10000, 15000]),
        (9500, 10000, [0, 5000, 10000]),
        (0, 10000, [0, 5000, 10000]),
        (180000, 200000, [0, 50000, 100000, 150000, 200000]),
    ],
)
def test_escala_do_grafico_tem_valores_redondos(maximo, topo, marcas):
    assert escala_bonita(maximo) == (topo, marcas)


def test_formatos_curtos_e_urgencia():
    assert centavos_para_reais_curto(150000) == "R$ 1.500"
    assert centavos_para_reais_curto(4290) == "R$ 42,90"
    assert [urgencia(m) for m in (0, 9, 10, 19, 20, 95)] == ["ok", "ok", "atencao", "atencao", "atrasado", "atrasado"]


@pytest.mark.parametrize(
    "nome, figura",
    [("Pratos", "prato"), ("Bebidas", "bebida"), ("Sucos naturais", "bebida"), ("Sobremesas", "sobremesa"),
     ("Lanches", "lanche"), ("Porções", "porcao"), ("Chá e cafés", "cafe"), ("Pratos na chapa", "prato"),
     ("Pizzas", "pizza"), ("", "prato")],
)
def test_figura_da_categoria_pelo_nome(nome, figura):
    assert figura_categoria(nome) == figura


def test_garcom_que_mais_vende_muda_conforme_as_vendas(db):
    rid = id_restaurante(db, SABOR)
    assert regras.resumo_do_dia(db, rid)["por_garcom"][0]["nome"] == "Bruno Lima"
    # Júlia fecha uma mesa com 2 moquecas (R$ 108,00) e passa o Bruno (R$ 156,80 x R$ 187,40)
    julia = id_usuario(db, "julia@sabordacasa.demo")
    pedido = regras.abrir_pedido(db, rid, id_mesa(db, rid, 9), julia)
    _lancar_e_entregar(db, rid, pedido, "Moqueca de peixe", 2)
    regras.registrar_pagamento(db, rid, pedido, "pix", regras.resumo_conta(db, rid, pedido)["total"])
    lider = regras.resumo_do_dia(db, rid)["por_garcom"][0]
    assert (lider["nome"], lider["contas"], lider["vendido"]) == ("Júlia Martins", 2, 7940 + 10800)
