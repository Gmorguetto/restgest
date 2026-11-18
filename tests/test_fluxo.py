"""Testes pelas telas (requisições HTTP), como um usuário faria no navegador."""
import pytest
from conftest import SABOR, consultar

from restaurante import regras
from restaurante.db import get_db
from restaurante.util import centavos_para_campo, centavos_para_reais


def test_fluxo_completo_da_mesa_ao_painel(app, entrar):
    """O fluxo da demonstração: garçom -> cozinha -> garçom -> caixa -> painel."""
    garcom = entrar("garcom@sabordacasa.demo")
    cozinha = entrar("cozinha@sabordacasa.demo")
    caixa = entrar("caixa@sabordacasa.demo")
    gerente = entrar("gerente@sabordacasa.demo")

    mesa5 = consultar(app, "SELECT m.id FROM mesa m JOIN restaurante r ON r.id = m.restaurante_id "
                           "WHERE r.nome = ? AND m.numero = 5", (SABOR,))[0]["id"]
    produtos = {p["nome"]: p["id"] for p in consultar(app, "SELECT id, nome FROM produto")}

    # 1. Garçom abre a mesa 5 e lança três itens
    resposta = garcom.post(f"/garcom/mesas/{mesa5}/abrir")
    assert resposta.status_code == 302
    pedido = int(resposta.headers["Location"].rstrip("/").split("/")[-1])
    for nome, quantidade, observacao in [
        ("Feijoada completa", 1, ""),
        ("Suco natural", 2, "sem açúcar"),
        ("Pudim de leite", 1, ""),
    ]:
        garcom.post(f"/garcom/pedidos/{pedido}/itens",
                    {"produto_id": produtos[nome], "quantidade": quantidade, "observacao": observacao})
    assert "Feijoada completa" in garcom.texto(f"/garcom/pedidos/{pedido}")

    # 2. Cozinha vê os itens com a observação e prepara
    fila = cozinha.texto("/cozinha/")
    assert "Mesa 5" in fila and "sem açúcar" in fila
    itens = [i["id"] for i in consultar(app, "SELECT id FROM item_pedido WHERE pedido_id = ?", (pedido,))]
    for item in itens:
        cozinha.post(f"/cozinha/itens/{item}/iniciar")
        cozinha.post(f"/cozinha/itens/{item}/pronto")

    # 3. Caixa ainda não consegue cobrar: os itens não foram entregues
    consumo = 4290 + 2 * 900 + 1200
    total = consumo + regras.valor_da_taxa(consumo, 10)  # com os 10% de serviço
    pagina = caixa.post(f"/caixa/pedidos/{pedido}/pagamentos",
                        {"forma": "pix", "valor": centavos_para_campo(total)}, follow_redirects=True)
    assert "não entregue" in pagina.get_data(as_text=True)

    # 4. Garçom vê os itens prontos no salão e entrega
    assert "Prontos para entregar" in garcom.texto("/garcom/mesas")
    for item in itens:
        garcom.post(f"/garcom/itens/{item}/entregar")

    # 5. Caixa fecha a conta por Pix e a mesa volta a ficar livre
    pagina = caixa.post(f"/caixa/pedidos/{pedido}/pagamentos",
                        {"forma": "pix", "valor": centavos_para_campo(total)}, follow_redirects=True)
    assert "Conta da mesa 5 fechada" in pagina.get_data(as_text=True)
    assert consultar(app, "SELECT status FROM mesa WHERE id = ?", (mesa5,))[0]["status"] == "livre"

    # 6. O painel do gerente soma a venda nova às de demonstração (R$ 259,82)
    painel = gerente.texto("/gerente/painel")
    assert centavos_para_reais(25982 + total) in painel
    assert centavos_para_reais(1158 + 794 + 410 + 729) in painel  # taxa de serviço do dia


def test_restaurantes_nao_veem_dados_um_do_outro(app, entrar):
    lanchonete = entrar("gerente@lanchonetedobairro.demo")
    pedido = consultar(app, "SELECT p.id FROM pedido p JOIN restaurante r ON r.id = p.restaurante_id "
                            "WHERE r.nome = ? AND p.status = 'aberto'", (SABOR,))[0]["id"]
    item = consultar(app, "SELECT id FROM item_pedido WHERE pedido_id = ? AND status = 'novo'", (pedido,))[0]["id"]

    assert lanchonete.get(f"/garcom/pedidos/{pedido}").status_code == 404
    assert lanchonete.get(f"/caixa/pedidos/{pedido}").status_code == 404
    assert "Feijoada" not in lanchonete.texto("/gerente/cardapio")
    assert "Moqueca" not in lanchonete.texto("/cozinha/")

    # Tentar mexer no item de outro restaurante não muda nada
    lanchonete.post(f"/cozinha/itens/{item}/iniciar")
    assert consultar(app, "SELECT status FROM item_pedido WHERE id = ?", (item,))[0]["status"] == "novo"


@pytest.mark.parametrize(
    "email, url, codigo",
    [
        ("garcom@sabordacasa.demo", "/gerente/painel", 403),
        ("garcom@sabordacasa.demo", "/caixa/", 403),
        ("cozinha@sabordacasa.demo", "/garcom/mesas", 403),
        ("caixa@sabordacasa.demo", "/cozinha/", 403),
        ("caixa@sabordacasa.demo", "/caixa/", 200),
        ("gerente@sabordacasa.demo", "/cozinha/", 200),  # gerente acessa tudo
    ],
)
def test_cada_perfil_acessa_so_a_sua_area(entrar, email, url, codigo):
    assert entrar(email).get(url).status_code == codigo


def test_visitante_e_mandado_para_o_login(visitante):
    resposta = visitante.get("/caixa/")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_formulario_sem_token_csrf_e_recusado(app, entrar):
    garcom = entrar("garcom@sabordacasa.demo")
    resposta = garcom.client.post("/garcom/mesas/1/abrir")  # sem csrf_token
    assert resposta.status_code == 400


def test_clique_duplo_em_entrar_nao_mostra_erro(entrar):
    gerente = entrar("gerente@sabordacasa.demo")
    # O segundo envio chega com o token antigo, de antes do login
    resposta = gerente.client.post("/login", data={"email": "x", "senha": "y", "csrf_token": "antigo"})
    assert resposta.status_code == 302
    assert gerente.get(resposta.headers["Location"], follow_redirects=True).status_code == 200


def test_senha_errada_nao_entra(visitante):
    pagina = visitante.post("/login", {"email": "gerente@sabordacasa.demo", "senha": "errada"},
                            follow_redirects=True).get_data(as_text=True)
    assert "E-mail ou senha incorretos" in pagina


def test_usuario_desativado_perde_o_acesso(app, entrar):
    gerente = entrar("gerente@sabordacasa.demo")
    caixa = entrar("caixa@sabordacasa.demo")
    assert "Diego Rocha" in gerente.texto("/gerente/equipe")
    caixa_id = consultar(app, "SELECT id FROM usuario WHERE email = 'caixa@sabordacasa.demo'")[0]["id"]
    gerente.post(f"/gerente/equipe/{caixa_id}/alternar")
    assert caixa.get("/caixa/").status_code == 302  # foi mandado para o login


def test_gerente_edita_produto_pela_tela(app, entrar):
    gerente = entrar("gerente@sabordacasa.demo")
    garcom = entrar("garcom@sabordacasa.demo")
    produto = consultar(app, "SELECT p.id, p.categoria_id FROM produto p JOIN restaurante r ON r.id = p.restaurante_id "
                             "WHERE r.nome = ? AND p.nome = 'Petit gâteau'", (SABOR,))[0]
    cardapio = gerente.texto("/gerente/cardapio")
    assert f'data-abrir="editar-{produto["id"]}"' in cardapio  # botão Editar e sua janela
    assert f'id="editar-{produto["id"]}"' in cardapio

    resposta = gerente.post(f"/gerente/produtos/{produto['id']}", {
        "nome": "Petit gâteau com sorvete", "categoria_id": produto["categoria_id"], "preco": "22,50", "ativo": "sim"})
    assert resposta.headers["Location"].endswith(f"#produto-{produto['id']}")
    pagina = gerente.texto("/gerente/cardapio")
    assert "Petit gâteau com sorvete" in pagina and "R$ 22,50" in pagina

    # O garçom já vê o produto novo ao lançar itens
    mesa = consultar(app, "SELECT id FROM mesa WHERE numero = 9 AND restaurante_id = "
                          "(SELECT id FROM restaurante WHERE nome = ?)", (SABOR,))[0]["id"]
    comanda = garcom.post(f"/garcom/mesas/{mesa}/abrir").headers["Location"]
    assert "Petit gâteau com sorvete · R$ 22,50" in garcom.texto(comanda)

    # Sem marcar "Disponível", o produto some para o garçom
    gerente.post(f"/gerente/produtos/{produto['id']}", {
        "nome": "Petit gâteau com sorvete", "categoria_id": produto["categoria_id"], "preco": "22,50"})
    assert "Petit gâteau com sorvete" not in garcom.texto(comanda)


def test_erro_ao_editar_volta_com_a_janela_aberta(app, entrar):
    gerente = entrar("gerente@sabordacasa.demo")
    produto = consultar(app, "SELECT id, categoria_id FROM produto WHERE nome = 'Pudim de leite'")[0]
    resposta = gerente.post(f"/gerente/produtos/{produto['id']}", {
        "nome": "Pudim", "categoria_id": produto["categoria_id"], "preco": "abc", "ativo": "sim"})
    assert resposta.headers["Location"].endswith(f"#editar-{produto['id']}")
    assert "Valor inválido" in gerente.texto("/gerente/cardapio")
    assert consultar(app, "SELECT nome FROM produto WHERE id = ?", (produto["id"],))[0]["nome"] == "Pudim de leite"


def _conta_pronta_para_cobrar(app, numero_mesa, produto="Moqueca de peixe"):
    """Prepara, direto pelas regras, uma comanda do Sabor da Casa com o item já entregue."""
    with app.app_context():
        db = get_db()
        rid = db.execute("SELECT id FROM restaurante WHERE nome = ?", (SABOR,)).fetchone()["id"]
        mesa = db.execute("SELECT id FROM mesa WHERE restaurante_id = ? AND numero = ?", (rid, numero_mesa)).fetchone()["id"]
        garcom = db.execute("SELECT id FROM usuario WHERE email = 'garcom@sabordacasa.demo'").fetchone()["id"]
        produto_id = db.execute("SELECT id FROM produto WHERE restaurante_id = ? AND nome = ?", (rid, produto)).fetchone()["id"]
        pedido = regras.abrir_pedido(db, rid, mesa, garcom)
        item = regras.adicionar_item(db, rid, pedido, produto_id, 1)
        for de, para in (("novo", "em_preparo"), ("em_preparo", "pronto"), ("pronto", "entregue")):
            regras.avancar_item(db, rid, item, de, para)
    return pedido


def test_caixa_retira_a_taxa_de_servico_pela_tela(app, entrar):
    caixa = entrar("caixa@sabordacasa.demo")
    pedido = _conta_pronta_para_cobrar(app, 8)
    pagina = caixa.texto(f"/caixa/pedidos/{pedido}")
    assert "Taxa de serviço (10%)" in pagina and "R$ 59,40" in pagina and "Retirar os 10%" in pagina

    pagina = caixa.post(f"/caixa/pedidos/{pedido}/taxa", {"acao": "retirar"}, follow_redirects=True).get_data(as_text=True)
    assert "Taxa de serviço retirada" in pagina and "não cobrada" in pagina and "Incluir 10% de serviço" in pagina

    pagina = caixa.post(f"/caixa/pedidos/{pedido}/pagamentos", {"forma": "cartao", "valor": "54,00"},
                        follow_redirects=True).get_data(as_text=True)
    assert "Conta da mesa 8 fechada" in pagina


def test_gerente_ajusta_a_taxa_pela_tela(entrar):
    gerente = entrar("gerente@sabordacasa.demo")
    assert "Ajustes do restaurante" in gerente.texto("/gerente/plano")
    pagina = gerente.post("/gerente/taxa-servico", {"cobrar": "sim", "percentual": "12"},
                          follow_redirects=True).get_data(as_text=True)
    assert "Taxa de serviço de 12% nas próximas comandas" in pagina and 'value="12"' in pagina
    pagina = gerente.post("/gerente/taxa-servico", {"percentual": "12"}, follow_redirects=True).get_data(as_text=True)
    assert "Taxa de serviço desligada" in pagina
    # As taxas já recebidas hoje continuam no painel, com o aviso de que a cobrança parou
    assert "cobrança está desligada" in gerente.texto("/gerente/painel")


def test_cadastro_de_novo_restaurante(visitante):
    resposta = visitante.post("/cadastro", {
        "restaurante": "Cantina da Esquina",
        "nome": "Joana",
        "email": "joana@cantina.com",
        "senha": "uma-senha-qualquer",
        "confirmacao": "uma-senha-qualquer",
    }, follow_redirects=True)
    pagina = resposta.get_data(as_text=True)
    assert "Painel do dia" in pagina and "Primeiros passos" in pagina
    assert "Cantina da Esquina" in pagina and "Teste grátis" in pagina
    # O restaurante novo começa vazio: não vê nada do Sabor da Casa
    assert "Feijoada" not in visitante.texto("/gerente/cardapio")


def test_cozinha_avanca_a_comanda_inteira_pela_tela(app, entrar):
    cozinha = entrar("cozinha@sabordacasa.demo")
    pedido = consultar(app, """SELECT p.id FROM pedido p JOIN mesa m ON m.id = p.mesa_id
                               WHERE m.numero = 2 AND p.status = 'aberto'""")[0]["id"]
    fila = cozinha.texto("/cozinha/")
    assert "Novos" in fila and "Em preparo" in fila and "Prontos" in fila
    assert "Aguardando o garçom buscar" in fila  # sobremesa pronta da mesa 4

    assert cozinha.post(f"/cozinha/pedidos/{pedido}/iniciar").status_code == 302
    assert cozinha.post(f"/cozinha/pedidos/{pedido}/pronto").status_code == 302
    status = {linha["status"] for linha in consultar(app, "SELECT status FROM item_pedido WHERE pedido_id = ?", (pedido,))}
    assert status == {"pronto"}

    # Segundo clique no mesmo botão: aviso, sem erro
    resposta = cozinha.post(f"/cozinha/pedidos/{pedido}/pronto", follow_redirects=True)
    assert resposta.status_code == 200 and "comanda mudou" in resposta.get_data(as_text=True)


def test_painel_mostra_vendas_situacao_e_formas_de_pagamento(entrar):
    painel = entrar("gerente@sabordacasa.demo").texto("/gerente/painel")
    for trecho in ("Recebido hoje", "R$ 259,82", "Vendas por hora", "Agora no restaurante",
                   "2 de 12", "Mesa 4: 1 item pronto aguardando o garçom",
                   "Formas de pagamento", "Pix", "Cartão", "Dinheiro", "Mais vendidos hoje",
                   "Garçom que mais vendeu hoje", "Bruno Lima", "Júlia Martins", "R$ 156,80 em 2 contas"):
        assert trecho in painel, trecho


def test_painel_sem_vendas_explica_o_que_falta(entrar):
    painel = entrar("gerente@lanchonetedobairro.demo").texto("/gerente/painel")
    assert "Nenhuma venda hoje ainda" in painel
    assert "Tudo em dia" in painel
    assert "ativar em Ajustes" in painel


def test_erro_ao_criar_produto_reabre_a_janela(app, entrar):
    gerente = entrar("gerente@sabordacasa.demo")
    categoria = consultar(app, "SELECT id FROM categoria WHERE nome = 'Pratos'")[0]["id"]
    resposta = gerente.post("/gerente/produtos", {"nome": "Bobó", "categoria_id": categoria, "preco": "xyz"})
    assert resposta.headers["Location"].endswith("#novo-produto")
    resposta = gerente.post("/gerente/produtos", {"nome": "Bobó de camarão", "categoria_id": categoria, "preco": "52"})
    novo = consultar(app, "SELECT id FROM produto WHERE nome = 'Bobó de camarão'")[0]["id"]
    assert resposta.headers["Location"].endswith(f"#produto-{novo}")
    cardapio = gerente.texto("/gerente/cardapio")
    assert 'data-nome="Bobó de camarão"' in cardapio and "Indisponíveis" in cardapio


def test_pagina_inicial_e_paginas_de_erro_com_figuras(visitante):
    inicio = visitante.texto("/")
    for trecho in ("Como funciona", "Feito para a correria do salão", "fig-heroi", "Criar meu restaurante",
                   "R$ 79,00", "R$ 119,00", "Implantação assistida", "R$ 600,00", "o código-fonte não está incluído",
                   "emissão de nota fiscal", "Gabriel Paulino Morguetto", "Pedro Rodrigues Barros"):
        assert trecho in inicio, trecho
    resposta = visitante.get("/pagina-que-nao-existe")
    assert resposta.status_code == 404 and "fig-media" in resposta.get_data(as_text=True)


def test_cozinha_sem_pedidos_mostra_cozinha_em_dia(entrar):
    fila = entrar("cozinha@lanchonetedobairro.demo").texto("/cozinha/")
    assert "Cozinha em dia" in fila and "quadro-cozinha" not in fila


def test_cardapio_mostra_figura_de_cada_categoria(entrar):
    cardapio = entrar("gerente@sabordacasa.demo").texto("/gerente/cardapio")
    for figura in ("fig-cat-prato", "fig-cat-bebida", "fig-cat-sobremesa"):
        assert figura in cardapio, figura


def test_login_de_demonstracao_separa_os_dois_garcons(visitante):
    login = visitante.texto("/login")
    assert "Garçom · Bruno" in login and "Garçom · Júlia" in login
    assert "Gerente · " not in login  # só repete o nome quando há dois do mesmo perfil
