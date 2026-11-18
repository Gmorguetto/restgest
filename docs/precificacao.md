# Do problema do cliente ao orçamento: precificação do RestGest

Este documento segue o método da apostila *Do problema do cliente ao orçamento de um sistema* (FATEC, Tópicos Especiais em Informática): entender o problema, definir o que será entregue, calcular o preço com uma base e transformar o cálculo em proposta. As contas são geradas por um script e conferem com os preços do sistema (`restaurante/regras.py`).

> **Valores de entrada são hipóteses do grupo**, exceto os que citam fonte. As respostas do cliente também são hipóteses: não foram confirmadas com um restaurante real e precisam ser validadas antes de vender.

## 1. Entenda o problema

| Pergunta ao cliente | Hipótese do grupo |
| --- | --- |
| Como vocês anotam e passam os pedidos hoje? | Comanda de papel: o garçom leva até a cozinha e o caixa soma a conta à mão. |
| Onde perdem tempo ou cometem erros? | Pedido trocado ou esquecido, observação perdida, cozinha sem ordem e demora para fechar a conta com os 10%. |
| Quem vai usar e quantas pessoas são? | Gerente, 1 a 4 garçons, cozinha e caixa; restaurantes de 5 a 40 mesas. |
| O que precisa funcionar primeiro? | O pedido do garçom chegar na cozinha e a conta fechar certa, com a taxa de serviço. |
| Precisa conectar a outro sistema? | Não na primeira versão: iFood, nota fiscal e maquininha ficam fora. |
| Existe prazo e faixa de investimento? | Começar em poucos dias, sem comprar equipamento, com mensalidade abaixo de R$ 150. |
| Quem decide e aprova a entrega? | O dono ou o gerente do restaurante. |

**Registro para confirmar com o cliente:** “Hoje vocês anotam os pedidos em comanda de papel e somam a conta à mão. O problema é que pedidos se perdem, a cozinha não sabe a ordem e fechar a conta com os 10% demora. A primeira entrega deve permitir lançar o pedido no celular, vê-lo na cozinha, fechar a conta com a taxa e ver o resumo do dia. Está correto?”

## 2. Defina o que será entregue

| Entra na primeira versão | Como conferir | Teste automático |
| --- | --- | --- |
| Cadastro do restaurante com 14 dias grátis | O restaurante criado entra no painel com o aviso dos dias de teste. | `test_cadastro_de_novo_restaurante` |
| Acesso por perfil (gerente, garçom, cozinha, caixa) | Cada pessoa só abre a tela do seu perfil; as outras respondem “sem permissão”. | `test_cada_perfil_acessa_so_a_sua_area` |
| Cardápio com categorias, preço e disponibilidade | O produto salvo aparece no cardápio; o desativado some da lista do garçom. | `test_edita_nome_categoria_preco_e_disponibilidade` |
| Mesas e equipe dentro do limite do plano | No Básico, a 11ª mesa e o 5º usuário são recusados. | `test_limite_de_mesas_do_plano` |
| Comanda por mesa, com observação nos itens | Uma segunda comanda na mesma mesa é recusada. | `test_nao_abre_duas_comandas_na_mesma_mesa` |
| Pedido na cozinha por ordem de chegada | O item aparece em Novos com a observação e passa a Em preparo e Pronto, sem pular etapas. | `test_item_segue_a_ordem_dos_status` |
| Conta com taxa de serviço opcional | Consumo de R$ 72,90 mostra total de R$ 80,19; sem a taxa, R$ 72,90. | `test_taxa_de_servico_entra_no_total` |
| Pagamento em dinheiro, cartão ou Pix | Dinheiro calcula troco; cartão acima do restante é recusado; o último pagamento libera a mesa. | `test_dinheiro_calcula_troco_e_libera_a_mesa` |
| Painel do dia | A conta paga aparece no recebido, no gráfico por hora e nas vendas por garçom. | `test_fluxo_completo_da_mesa_ao_painel` |
| Dados separados por restaurante | Um restaurante não vê nem altera os dados de outro. | `test_restaurantes_nao_veem_dados_um_do_outro` |

**Fica fora desta versão:** aplicativo para Android ou iPhone (o sistema funciona no navegador); cardápio por QR code e pedido feito pelo cliente; delivery e integração com iFood ou WhatsApp; emissão de nota fiscal (NFC-e); impressora de cozinha e maquininha de cartão integradas; controle de estoque; várias unidades na mesma conta; importação automática do cardápio de outros sistemas; relatórios por semana ou por mês.

**Condições:**

- O restaurante fornece o cardápio com categorias e preços, o número das mesas e o nome e o e-mail de cada pessoa da equipe.
- O restaurante usa os aparelhos que já tem: celular com navegador para os garçons, computador ou tablet para o caixa e o gerente, TV ou tablet na cozinha (opcional) e internet no salão.
- No autoatendimento, o próprio dono cadastra tudo pelos “Primeiros passos” do painel, sem custo.
- Na implantação assistida, o prazo começa depois da aprovação, do pagamento inicial e do recebimento dessas informações.

**Suporte e mudanças:**

- Canais: e-mail e WhatsApp, de segunda a sexta, das 9h às 18h.
- Primeira resposta: até 1 dia útil no Básico e até 4 horas úteis no Profissional.
- Orientação incluída: 30 min por mês no Básico e 1 hora por mês no Profissional (não acumula).
- Erro, quando o sistema não faz o que o escopo descreve: correção sem custo.
- Função nova: registrar o pedido, estimar custo e prazo (base de R$ 50/h) e pedir aprovação antes de começar.
- Hospedagem, backup e atualizações estão incluídos na mensalidade.
- A assinatura dá acesso ao sistema pela internet enquanto estiver ativa; o código-fonte não está incluído. Os dados cadastrados são do restaurante.
- Sem taxa de adesão e sem fidelidade: o cancelamento vale no fim do mês pago.

## 3. Calcule o preço com uma base

### Custo por hora

Remuneração desejada (R$ 2.600,00) + despesas mensais (R$ 400,00) = R$ 3.000,00. Com 60 horas vendáveis por mês (meio período, porque nem toda hora pode ser vendida): **R$ 50,00 por hora**.

### Investimento no MVP

| Etapa | Horas estimadas |
| --- | --- |
| Conversa, levantamento e escopo | 12 h |
| Desenho das telas e do fluxo | 16 h |
| Desenvolvimento | 110 h |
| Testes e ajustes | 30 h |
| Documentação, implantação piloto e orientação | 16 h |
| Reuniões e acompanhamento | 16 h |
| **Total** | **200 h** |

| Componente | Valor |
| --- | --- |
| Trabalho: 200 h × R$ 50,00 | R$ 10.000,00 |
| Despesas do projeto: domínio e 2 meses de servidor de testes | R$ 179,98 |
| Reserva para imprevistos do escopo (10%) | R$ 1.000,00 |
| **Investimento a recuperar** | **R$ 11.179,98** |

Parte do código foi feita com ajuda de IA (ver `docs/uso-de-ia.md`); as horas acima são a estimativa do grupo para levantar, revisar, testar e documentar o produto e devem ser ajustadas ao tempo real registrado. O investimento é recuperado em 24 meses: **R$ 465,83 por mês**.

### Custos fixos mensais da operação

| Custo | Por mês |
| --- | --- |
| Servidor VPS (Hostinger KVM 2, preço de renovação) | R$ 69,99 |
| Domínio .com.br (R$ 40 por ano) | R$ 3,33 |
| Backup externo e monitoramento (estimativa) | R$ 15,00 |
| Manutenção do produto: 10 h × custo/hora | R$ 500,00 |
| Contabilidade (estimativa) | R$ 200,00 |
| Retorno do investimento no MVP (24 meses) | R$ 465,83 |
| **Total** | **R$ 1.254,16** |

Rateio pela meta de 40 restaurantes: R$ 1.254,16 ÷ 40 = **R$ 31,35 por cliente**.

### Mensalidade pelo markup (Sebrae)

Preço sugerido = custos por cliente ÷ (1 − tributos − reserva − lucro) = custos ÷ (1 − 6% − 5% − 15%) = custos ÷ 0,74.

| Componente | Básico | Profissional |
| --- | --- | --- |
| Rateio do custo fixo | R$ 31,35 | R$ 31,35 |
| Suporte (0,5 h e 1 h × R$ 50) | R$ 25,00 | R$ 50,00 |
| Taxa de cobrança (Pix ou boleto) | R$ 1,99 | R$ 1,99 |
| **Custo por cliente** | **R$ 58,34** | **R$ 83,34** |
| Preço sugerido (÷ 0,74) | R$ 78,84 | R$ 112,63 |
| **Preço definido** | **R$ 79,00** | **R$ 119,00** |

O preço definido arredonda o sugerido para cima, terminando em 9. Tributos: provisão de 6% (Simples Nacional, Anexo III, alíquota inicial). Pode ser 15,5% (Anexo V) conforme o CNAE e o Fator R; confirmar com o contador.

### Ponto de equilíbrio

Margem de contribuição por cliente (preço − suporte − cobrança − tributos − reserva): Básico R$ 43,32, Profissional R$ 53,92. Com metade dos clientes em cada plano, os custos fixos são cobertos a partir de **26 restaurantes**.

| Restaurantes | Receita | Custos | Resultado |
| --- | --- | --- | --- |
| 10 | R$ 990,00 | R$ 1.757,96 | R$ -767,96 (-78%) |
| 20 | R$ 1.980,00 | R$ 2.261,76 | R$ -281,76 (-14%) |
| 26 | R$ 2.574,00 | R$ 2.564,04 | R$ 9,96 (0%) |
| 30 | R$ 2.970,00 | R$ 2.765,56 | R$ 204,44 (7%) |
| 40 | R$ 3.960,00 | R$ 3.269,36 | R$ 690,64 (17%) |
| 50 | R$ 4.950,00 | R$ 3.773,16 | R$ 1,176,84 (24%) |

### Implantação assistida (opcional)

| Etapa | Horas |
| --- | --- |
| Conversa e levantamento com o responsável | 1 h |
| Cadastro do cardápio, das mesas e da equipe | 2 h |
| Orientação da equipe no restaurante | 2 h |
| Acompanhamento do primeiro turno | 2 h |
| Organização e deslocamento | 1 h |
| **Total** | **8 h** |

| Componente | Valor |
| --- | --- |
| Trabalho: 8 h × R$ 50 | R$ 400,00 |
| Despesas específicas (deslocamento) | R$ 40,00 |
| Reserva para imprevistos do escopo | R$ 40,00 |
| Provisão de tributos (6%) e taxas de cobrança | R$ 41,97 |
| Lucro planejado | R$ 78,03 |
| **Preço proposto** | **R$ 600,00** |

Pagamento por marcos: 40% na aprovação: R$ 240,00; 30% com o cadastro conferido pelo responsável: R$ 180,00; 30% após o aceite (primeiro turno acompanhado): R$ 180,00. 8 horas são esforço de trabalho; 5 dias úteis são prazo de calendário.

### Comparação com o mercado

| Sistema | Preço | O que entrega |
| --- | --- | --- |
| Saipos | a partir de R$ 240,79/mês | Gestão completa: estoque, financeiro, nota fiscal e iFood; implantação gratuita |
| MenuTiger (plano Regular) | US$ 17/mês | Pedidos online e ponto de venda; limite de 500 pedidos por mês |
| RestGest | R$ 79 a R$ 119/mês | Comanda, cozinha, caixa e painel do dia; sem nota fiscal, estoque nem delivery |

O RestGest fica abaixo dos sistemas completos porque entrega menos, e o preço cobre os custos a partir de 26 restaurantes. Preços consultados em 18/11/2026.

## 4. Proposta (modelo)

| Campo | Proposta |
| --- | --- |
| Cliente e responsável | Restaurante Sabor da Casa (cliente fictício, usado na demonstração) e [nome de quem aprova]. |
| Objetivo | Organizar pedidos, cozinha e caixa e acompanhar as vendas do dia. |
| Entrega | Assinatura do RestGest no plano Profissional (40 mesas, 10 usuários) e implantação assistida: cadastro do cardápio, das mesas e da equipe, orientação no restaurante e acompanhamento do primeiro turno. |
| Fora do escopo | Aplicativo para celular, QR code e pedido pelo cliente, iFood e WhatsApp, nota fiscal, impressora e maquininha integradas, estoque, várias unidades e importação automática. |
| Preço de implantação | R$ 600,00 para o escopo descrito. |
| Pagamento por marcos | 40% na aprovação: R$ 240,00. 30% com o cadastro conferido pelo responsável: R$ 180,00. 30% após o aceite: R$ 180,00. |
| Prazo estimado | 5 dias úteis depois da aprovação, do pagamento inicial e do recebimento do cardápio, das mesas e da equipe. |
| Custos recorrentes | Mensalidade de R$ 119,00 a partir do fim dos 14 dias grátis, cobrada por Pix, boleto ou cartão. Inclui hospedagem, backup, atualizações e suporte. Não está incluída nos R$ 600,00. |
| Entrega e aceite | Conferência das 10 funções da tabela de escopo com o responsável, no restaurante. |
| Suporte e mudanças | E-mail e WhatsApp em dias úteis, das 9h às 18h, com resposta em até 4 horas úteis e 1 hora de orientação por mês. Correção de erro sem custo; função nova exige novo orçamento. |
| Acesso | Acesso ao sistema pela internet enquanto a assinatura estiver ativa; código-fonte não incluído. |
| Validade da proposta | 10 dias corridos a partir da data de envio. |

Antes de enviar: conferir as somas, os marcos de pagamento e o que o cliente precisa fornecer, e pedir aprovação por escrito.

### Resposta a um pedido extra

**Cliente:** “Inclui também cardápio por QR code e integração com o iFood pelo mesmo preço?”

**Resposta:** Esses dois itens não estão no escopo desta proposta. Podemos registrar o pedido e, depois de entender como vocês usam o iFood hoje, enviar um orçamento separado com preço e prazo. A proposta atual continua valendo como está.

## Fontes

- FATEC, Tópicos Especiais em Informática: Do problema do cliente ao orçamento de um sistema (2026)
- [Sebrae PR: Precificação de produtos (markup)](https://sebraepr.com.br/comunidade/artigo/precificacao-de-produtos-como-o-pequeno-empreendedor-define-o-preco-certo)
- [Agilize: Simples Nacional para software, Anexo III ou V](https://agilize.com.br/artigos/simples-nacional-para-software)
- [Asaas: Preços e taxas](https://www.asaas.com/precos-e-taxas)
- [Hora de Codar: Quanto custa uma VPS, preço atualizado 2026](https://horadecodar.com.br/valor-vps/)
- [Teletime: .br chega a 6 milhões de domínios (registro a R$ 40 por ano)](https://teletime.com.br/14/10/2026/br-6-milhoes/)
- [Saipos: Sistema para restaurante (perguntas frequentes)](https://saipos.com/sistema/restaurante)
- [MenuTiger: Preços](https://www.menutiger.com/pt/pricing)

Consultadas em 18/11/2026. Para refazer e conferir as contas: `python docs/precificacao.py`.
