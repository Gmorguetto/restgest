# Registro de uso de inteligência artificial

O enunciado pede que o PDF informe quais ferramentas de IA o grupo usou, em quais etapas e pelo menos um exemplo concreto. Anotem aqui cada uso relevante no mesmo dia em que ele acontecer.

## Registro

| Data | Ferramenta | Etapa | O que pedimos | O que a IA entregou | O que o grupo verificou ou mudou |
| --- | --- | --- | --- | --- | --- |
| 17/11/2026 | Claude (Anthropic) | Planejamento | Plano do projeto, da organização à apresentação, para um sistema de gestão de restaurante | Escopo do MVP, fluxo da demonstração, cronograma de 17 a 23/11, modelo de dados, estrutura do PDF, roteiro e perguntas prováveis | (preencher) |
| 17/11/2026 | Claude (Anthropic) | Programação, testes e documentação | Desenvolver a aplicação seguindo o plano | Primeira versão completa em Flask e SQLite: telas dos quatro perfis, regras de negócio, 44 testes automáticos, dados de demonstração, README e capturas de tela | (preencher: quem revisou cada arquivo e o que foi alterado) |
| (data) | (ferramenta) | (etapa) | | | |

## Revisão do código gerado

O professor pode perguntar sobre qualquer parte do código. Cada integrante fica responsável por ler, rodar e saber explicar um grupo de arquivos:

| Arquivos | Responsável | Pontos para saber explicar |
| --- | --- | --- |
| `schema.sql`, `db.py` | (preencher) | As 8 tabelas, `restaurante_id`, preço em centavos, índice único da mesa |
| `regras.py`, `util.py` | (preencher) | Abrir comanda, status dos itens, total, pagamento com troco, limites do plano |
| `auth.py`, `__init__.py` | (preencher) | Login com hash, sessão, `perfil_requerido`, proteção CSRF |
| `gerente.py`, `garcom.py`, `cozinha.py`, `caixa.py`, `templates/` | (preencher) | Como uma rota recebe o formulário, chama a regra e redireciona |
| `tests/` | (preencher) | O que cada teste confere e como rodar |

## Ideias de exemplo concreto para o PDF

Escolham um caso que o grupo realmente conferiu e contem com as palavras de vocês: o que foi pedido, o que a IA propôs, como o grupo testou e o que mudou. Dois casos que aconteceram nesta versão:

- **Dois garçons abrindo a mesma mesa.** A IA propôs um índice único no banco (`um_pedido_aberto_por_mesa`), que impede duas comandas abertas na mesma mesa mesmo quando a verificação do programa chega atrasada. O teste `test_indice_do_banco_impede_comanda_dupla_mesmo_com_corrida` simula a situação.
- **Revisão visual das telas.** Na primeira versão, o selo "Ocupada desde 18:12" vazava do cartão da mesa no celular e a lista de produtos mostrava "Água mineral" no fim, porque o banco ordena letras acentuadas depois do Z. Os dois defeitos foram vistos nas capturas de tela e corrigidos; a ordem alfabética ganhou um teste.
