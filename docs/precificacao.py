"""Memória de cálculo do preço do RestGest (método da apostila + markup do Sebrae).

Todos os valores de entrada são hipóteses do grupo, exceto os marcados como "fonte".
Rodar este arquivo imprime as contas e confere se os preços do sistema batem com elas.
"""
from math import ceil

# ---------- 1. Custo por hora (apostila, seção 3)
REMUNERACAO_DESEJADA = 2600.00     # por integrante, meio período
DESPESAS_MENSAIS = 400.00          # internet, energia, computador, ferramentas
HORAS_VENDAVEIS = 60               # nem toda hora do mês pode ser vendida
CUSTO_HORA = (REMUNERACAO_DESEJADA + DESPESAS_MENSAIS) / HORAS_VENDAVEIS   # R$ 50

# ---------- 2. Investimento no MVP (horas por etapa)
ETAPAS_MVP = [
    ("Conversa, levantamento e escopo", 12),
    ("Desenho das telas e do fluxo", 16),
    ("Desenvolvimento", 110),
    ("Testes e ajustes", 30),
    ("Documentação, implantação piloto e orientação", 16),
    ("Reuniões e acompanhamento", 16),
]
HORAS_MVP = sum(h for _, h in ETAPAS_MVP)                 # 200 h
TRABALHO_MVP = HORAS_MVP * CUSTO_HORA                     # R$ 10.000
DESPESAS_MVP = 40.00 + 2 * 69.99                          # domínio + 2 meses de servidor de testes
RESERVA_MVP = 0.10 * TRABALHO_MVP                         # imprevistos do escopo
INVESTIMENTO = TRABALHO_MVP + DESPESAS_MVP + RESERVA_MVP  # R$ 11.179,98
MESES_RETORNO = 24
AMORTIZACAO = INVESTIMENTO / MESES_RETORNO

# ---------- 3. Custos fixos mensais da operação
FIXOS = [
    ("Servidor VPS (Hostinger KVM 2, preço de renovação)", 69.99),       # fonte: horadecodar.com.br
    ("Domínio .com.br (R$ 40 por ano)", 40.00 / 12),                      # fonte: Registro.br
    ("Backup externo e monitoramento (estimativa)", 15.00),
    ("Manutenção do produto: 10 h × custo/hora", 10 * CUSTO_HORA),
    ("Contabilidade (estimativa)", 200.00),
    ("Retorno do investimento no MVP (24 meses)", AMORTIZACAO),
]
TOTAL_FIXO = sum(v for _, v in FIXOS)
META_CLIENTES = 40                    # meta para rateio do custo fixo
RATEIO = TOTAL_FIXO / META_CLIENTES

# ---------- 4. Percentuais sobre o preço (markup divisor do Sebrae)
TRIBUTOS = 0.06       # fonte: Simples Nacional, Anexo III, alíquota inicial (confirmar com contador)
RESERVA = 0.05        # imprevistos e inadimplência
LUCRO = 0.15          # lucro planejado
DIVISOR = 1 - (TRIBUTOS + RESERVA + LUCRO)    # 0,74
TAXA_COBRANCA = 1.99  # fonte: Asaas, tarifa padrão por Pix ou boleto recebido

PLANOS = {
    "basico": {"nome": "Básico", "horas_suporte": 0.5, "preco": 79},
    "profissional": {"nome": "Profissional", "horas_suporte": 1.0, "preco": 119},
}


def composicao(chave):
    p = PLANOS[chave]
    suporte = p["horas_suporte"] * CUSTO_HORA
    custo_direto = RATEIO + suporte + TAXA_COBRANCA
    sugerido = custo_direto / DIVISOR
    preco = p["preco"]
    return {
        "suporte": suporte, "custo_direto": custo_direto, "sugerido": sugerido, "preco": preco,
        "tributos": TRIBUTOS * preco, "reserva": RESERVA * preco,
        "margem_contribuicao": preco - suporte - TAXA_COBRANCA - (TRIBUTOS + RESERVA) * preco,
        "lucro": preco - custo_direto - (TRIBUTOS + RESERVA) * preco,
    }


# ---------- 5. Ponto de equilíbrio (metade dos clientes em cada plano)
def resultado_mensal(clientes):
    metade = clientes / 2
    receita = metade * (PLANOS["basico"]["preco"] + PLANOS["profissional"]["preco"])
    variaveis = sum(metade * (composicao(c)["suporte"] + TAXA_COBRANCA) for c in PLANOS)
    percentuais = (TRIBUTOS + RESERVA) * receita
    custo_total = TOTAL_FIXO + variaveis + percentuais
    return receita, custo_total, receita - custo_total


def ponto_de_equilibrio():
    margem_media = (composicao("basico")["margem_contribuicao"] + composicao("profissional")["margem_contribuicao"]) / 2
    return TOTAL_FIXO / margem_media


# ---------- 6. Implantação assistida (opcional, por restaurante)
ETAPAS_IMPLANTACAO = [
    ("Conversa e levantamento com o responsável", 1),
    ("Cadastro do cardápio, das mesas e da equipe", 2),
    ("Orientação da equipe no restaurante", 2),
    ("Acompanhamento do primeiro turno", 2),
    ("Organização e deslocamento", 1),
]
HORAS_IMPLANTACAO = sum(h for _, h in ETAPAS_IMPLANTACAO)          # 8 h
IMPLANTACAO = [
    ("Trabalho: 8 h × R$ 50", HORAS_IMPLANTACAO * CUSTO_HORA),       # 400
    ("Despesas específicas (deslocamento)", 40.00),
    ("Reserva para imprevistos do escopo", 40.00),
    ("Provisão de tributos (6%) e taxas de cobrança", 0.06 * 600 + 3 * TAXA_COBRANCA),
    ("Lucro planejado", None),                                         # o que sobra até R$ 600
]
PRECO_IMPLANTACAO = 600.00
_soma_sem_lucro = sum(v for _, v in IMPLANTACAO if v is not None)
IMPLANTACAO[-1] = ("Lucro planejado", PRECO_IMPLANTACAO - _soma_sem_lucro)
MARCOS_IMPLANTACAO = [("40% na aprovação", 0.40), ("30% com o cadastro conferido pelo responsável", 0.30),
                      ("30% após o aceite (primeiro turno acompanhado)", 0.30)]


def reais(valor):
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


if __name__ == "__main__":
    print("custo/hora", reais(CUSTO_HORA))
    print("investimento", HORAS_MVP, "h", reais(TRABALHO_MVP), reais(DESPESAS_MVP), reais(RESERVA_MVP), "=", reais(INVESTIMENTO),
          "| amortização/mês", reais(AMORTIZACAO))
    for nome, v in FIXOS:
        print(f"  {nome}: {reais(v)}")
    print("total fixo", reais(TOTAL_FIXO), "| rateio por cliente (40)", reais(RATEIO), "| divisor", DIVISOR)
    for c in PLANOS:
        k = composicao(c)
        print(c, {x: round(y, 2) for x, y in k.items()})
    print("ponto de equilíbrio", round(ponto_de_equilibrio(), 1), "clientes ->", ceil(ponto_de_equilibrio()))
    for n in (10, 20, 26, 30, 40, 50):
        r, ct, res = resultado_mensal(n)
        print(f"  {n} clientes: receita {reais(r)} custo {reais(ct)} resultado {reais(res)} ({res / r:.1%})")
    print("implantação", [(n, round(v, 2)) for n, v in IMPLANTACAO], "=", sum(v for _, v in IMPLANTACAO))
    print("marcos", [(n, PRECO_IMPLANTACAO * p) for n, p in MARCOS_IMPLANTACAO])
    # os preços escolhidos precisam cobrir o preço sugerido pelo markup
    for c in PLANOS:
        k = composicao(c)
        assert k["preco"] >= k["sugerido"], c
    assert abs(sum(v for _, v in IMPLANTACAO) - PRECO_IMPLANTACAO) < 0.01
    # e os preços do sistema precisam ser os desta memória de cálculo
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        from restaurante import regras
    except ImportError:
        print("(sistema não encontrado: rode a partir da pasta do projeto para conferir os preços)")
    else:
        for c in PLANOS:
            assert regras.PLANOS[c]["preco_centavos"] == PLANOS[c]["preco"] * 100, c
        assert regras.IMPLANTACAO["preco_centavos"] == PRECO_IMPLANTACAO * 100
        print("preços do sistema conferem com a memória de cálculo")


# =====================================================================================
# Conteúdo do orçamento (usado no PDF e no docs/precificacao.md, para dizerem o mesmo)
# =====================================================================================
PERGUNTAS = [
    ("Como vocês anotam e passam os pedidos hoje?", "Comanda de papel: o garçom leva até a cozinha e o caixa soma a conta à mão."),
    ("Onde perdem tempo ou cometem erros?", "Pedido trocado ou esquecido, observação perdida, cozinha sem ordem e demora para fechar a conta com os 10%."),
    ("Quem vai usar e quantas pessoas são?", "Gerente, 1 a 4 garçons, cozinha e caixa; restaurantes de 5 a 40 mesas."),
    ("O que precisa funcionar primeiro?", "O pedido do garçom chegar na cozinha e a conta fechar certa, com a taxa de serviço."),
    ("Precisa conectar a outro sistema?", "Não na primeira versão: iFood, nota fiscal e maquininha ficam fora."),
    ("Existe prazo e faixa de investimento?", "Começar em poucos dias, sem comprar equipamento, com mensalidade abaixo de R$ 150."),
    ("Quem decide e aprova a entrega?", "O dono ou o gerente do restaurante."),
]
REGISTRO = ("Hoje vocês anotam os pedidos em comanda de papel e somam a conta à mão. O problema é que pedidos se perdem, "
            "a cozinha não sabe a ordem e fechar a conta com os 10% demora. A primeira entrega deve permitir lançar o pedido "
            "no celular, vê-lo na cozinha, fechar a conta com a taxa e ver o resumo do dia. Está correto?")

ESCOPO = [
    ("Cadastro do restaurante com 14 dias grátis", "O restaurante criado entra no painel com o aviso dos dias de teste.", "test_cadastro_de_novo_restaurante"),
    ("Acesso por perfil (gerente, garçom, cozinha, caixa)", "Cada pessoa só abre a tela do seu perfil; as outras respondem “sem permissão”.", "test_cada_perfil_acessa_so_a_sua_area"),
    ("Cardápio com categorias, preço e disponibilidade", "O produto salvo aparece no cardápio; o desativado some da lista do garçom.", "test_edita_nome_categoria_preco_e_disponibilidade"),
    ("Mesas e equipe dentro do limite do plano", "No Básico, a 11ª mesa e o 5º usuário são recusados.", "test_limite_de_mesas_do_plano"),
    ("Comanda por mesa, com observação nos itens", "Uma segunda comanda na mesma mesa é recusada.", "test_nao_abre_duas_comandas_na_mesma_mesa"),
    ("Pedido na cozinha por ordem de chegada", "O item aparece em Novos com a observação e passa a Em preparo e Pronto, sem pular etapas.", "test_item_segue_a_ordem_dos_status"),
    ("Conta com taxa de serviço opcional", "Consumo de R$ 72,90 mostra total de R$ 80,19; sem a taxa, R$ 72,90.", "test_taxa_de_servico_entra_no_total"),
    ("Pagamento em dinheiro, cartão ou Pix", "Dinheiro calcula troco; cartão acima do restante é recusado; o último pagamento libera a mesa.", "test_dinheiro_calcula_troco_e_libera_a_mesa"),
    ("Painel do dia", "A conta paga aparece no recebido, no gráfico por hora e nas vendas por garçom.", "test_fluxo_completo_da_mesa_ao_painel"),
    ("Dados separados por restaurante", "Um restaurante não vê nem altera os dados de outro.", "test_restaurantes_nao_veem_dados_um_do_outro"),
]
FORA_EXTRA = ["importação automática do cardápio de outros sistemas", "relatórios por semana ou por mês"]

CONDICOES = [
    "O restaurante fornece o cardápio com categorias e preços, o número das mesas e o nome e o e-mail de cada pessoa da equipe.",
    "O restaurante usa os aparelhos que já tem: celular com navegador para os garçons, computador ou tablet para o caixa e o gerente, "
    "TV ou tablet na cozinha (opcional) e internet no salão.",
    "No autoatendimento, o próprio dono cadastra tudo pelos “Primeiros passos” do painel, sem custo.",
    "Na implantação assistida, o prazo começa depois da aprovação, do pagamento inicial e do recebimento dessas informações.",
]
SUPORTE = [
    "Canais: e-mail e WhatsApp, de segunda a sexta, das 9h às 18h.",
    "Primeira resposta: até 1 dia útil no Básico e até 4 horas úteis no Profissional.",
    "Orientação incluída: 30 min por mês no Básico e 1 hora por mês no Profissional (não acumula).",
    "Erro, quando o sistema não faz o que o escopo descreve: correção sem custo.",
    "Função nova: registrar o pedido, estimar custo e prazo (base de R$ 50/h) e pedir aprovação antes de começar.",
    "Hospedagem, backup e atualizações estão incluídos na mensalidade.",
    "A assinatura dá acesso ao sistema pela internet enquanto estiver ativa; o código-fonte não está incluído. Os dados cadastrados são do restaurante.",
    "Sem taxa de adesão e sem fidelidade: o cancelamento vale no fim do mês pago.",
]

PROPOSTA = [
    ("Cliente e responsável", "Restaurante Sabor da Casa (cliente fictício, usado na demonstração) e [nome de quem aprova]."),
    ("Objetivo", "Organizar pedidos, cozinha e caixa e acompanhar as vendas do dia."),
    ("Entrega", "Assinatura do RestGest no plano Profissional (40 mesas, 10 usuários) e implantação assistida: cadastro do cardápio, "
                "das mesas e da equipe, orientação no restaurante e acompanhamento do primeiro turno."),
    ("Fora do escopo", "Aplicativo para celular, QR code e pedido pelo cliente, iFood e WhatsApp, nota fiscal, impressora e maquininha "
                       "integradas, estoque, várias unidades e importação automática."),
    ("Preço de implantação", "R$ 600,00 para o escopo descrito."),
    ("Pagamento por marcos", "40% na aprovação: R$ 240,00. 30% com o cadastro conferido pelo responsável: R$ 180,00. "
                             "30% após o aceite: R$ 180,00."),
    ("Prazo estimado", "5 dias úteis depois da aprovação, do pagamento inicial e do recebimento do cardápio, das mesas e da equipe."),
    ("Custos recorrentes", "Mensalidade de R$ 119,00 a partir do fim dos 14 dias grátis, cobrada por Pix, boleto ou cartão. "
                           "Inclui hospedagem, backup, atualizações e suporte. Não está incluída nos R$ 600,00."),
    ("Entrega e aceite", "Conferência das 10 funções da tabela de escopo com o responsável, no restaurante."),
    ("Suporte e mudanças", "E-mail e WhatsApp em dias úteis, das 9h às 18h, com resposta em até 4 horas úteis e 1 hora de orientação "
                           "por mês. Correção de erro sem custo; função nova exige novo orçamento."),
    ("Acesso", "Acesso ao sistema pela internet enquanto a assinatura estiver ativa; código-fonte não incluído."),
    ("Validade da proposta", "10 dias corridos a partir da data de envio."),
]
PEDIDO_EXTRA = ("“Inclui também cardápio por QR code e integração com o iFood pelo mesmo preço?”",
                "Esses dois itens não estão no escopo desta proposta. Podemos registrar o pedido e, depois de entender "
                "como vocês usam o iFood hoje, enviar um orçamento separado com preço e prazo. A proposta atual continua "
                "valendo como está.")

MERCADO = [
    ("Saipos", "a partir de R$ 240,79/mês", "Gestão completa: estoque, financeiro, nota fiscal e iFood; implantação gratuita"),
    ("MenuTiger (plano Regular)", "US$ 17/mês", "Pedidos online e ponto de venda; limite de 500 pedidos por mês"),
    ("RestGest", "R$ 79 a R$ 119/mês", "Comanda, cozinha, caixa e painel do dia; sem nota fiscal, estoque nem delivery"),
]
FONTES = [
    ("FATEC, Tópicos Especiais em Informática: Do problema do cliente ao orçamento de um sistema (2026)", None),
    ("Sebrae PR: Precificação de produtos (markup)", "https://sebraepr.com.br/comunidade/artigo/precificacao-de-produtos-como-o-pequeno-empreendedor-define-o-preco-certo"),
    ("Agilize: Simples Nacional para software, Anexo III ou V", "https://agilize.com.br/artigos/simples-nacional-para-software"),
    ("Asaas: Preços e taxas", "https://www.asaas.com/precos-e-taxas"),
    ("Hora de Codar: Quanto custa uma VPS, preço atualizado 2026", "https://horadecodar.com.br/valor-vps/"),
    ("Teletime: .br chega a 6 milhões de domínios (registro a R$ 40 por ano)", "https://teletime.com.br/14/10/2026/br-6-milhoes/"),
    ("Saipos: Sistema para restaurante (perguntas frequentes)", "https://saipos.com/sistema/restaurante"),
    ("MenuTiger: Preços", "https://www.menutiger.com/pt/pricing"),
]
