"""Dados fictícios para a demonstração e para os testes automáticos.

Cria dois restaurantes para mostrar que os dados de cada cliente ficam
separados. A senha dos usuários de demonstração NÃO fica no código: vem da
variável SENHA_DEMO (arquivo .env) ou é digitada no terminal.

Os dados passam pelas mesmas funções de regras.py que as telas usam, então
também servem de teste das regras.
"""
import os
from datetime import datetime

import click

from . import regras
from .db import get_db, init_db

RESTAURANTES = [
    {
        "nome": "Restaurante Sabor da Casa",
        "dominio": "sabordacasa.demo",
        "plano": "profissional",
        "taxa_servico": 10,
        "equipe": [  # (nome, perfil[, início do e-mail quando não é o próprio perfil])
            ("Ana Souza", "gerente"),
            ("Bruno Lima", "garcom"),
            ("Júlia Martins", "garcom", "julia"),
            ("Carla Mendes", "cozinha"),
            ("Diego Rocha", "caixa"),
        ],
        "cardapio": {
            "Pratos": [
                ("Feijoada completa", 4290),
                ("Filé à parmegiana", 4890),
                ("Frango grelhado com legumes", 3650),
                ("Moqueca de peixe", 5400),
            ],
            "Bebidas": [
                ("Refrigerante lata", 650),
                ("Suco natural", 900),
                ("Água mineral", 450),
                ("Cerveja long neck", 1200),
            ],
            "Sobremesas": [("Pudim de leite", 1200), ("Petit gâteau", 1890)],
        },
        "mesas": 12,
    },
    {
        "nome": "Lanchonete do Bairro",
        "dominio": "lanchonetedobairro.demo",
        "plano": "basico",
        "taxa_servico": 0,
        "equipe": [
            ("Eduardo Alves", "gerente"),
            ("Fernanda Dias", "garcom"),
            ("Gabriel Costa", "cozinha"),
        ],
        "cardapio": {
            "Lanches": [("X-Burger", 2200), ("X-Salada", 2400), ("Misto quente", 1200)],
            "Bebidas": [("Refrigerante lata", 600), ("Suco de laranja", 800)],
        },
        "mesas": 6,
    },
]

# Contas já pagas hoje: (mesa, [(produto, quantidade)], forma de pagamento, minutos atrás, quem atendeu)
CONTAS_FECHADAS = [
    (3, [("Feijoada completa", 2), ("Suco natural", 2), ("Pudim de leite", 1)], "pix", 95, "garcom"),
    (7, [("Filé à parmegiana", 1), ("Cerveja long neck", 2), ("Refrigerante lata", 1)], "cartao", 70, "julia"),
    (1, [("Frango grelhado com legumes", 1), ("Água mineral", 1)], "dinheiro", 40, "garcom"),
]
# Mesas em atendimento agora: (mesa, [(produto, quantidade, status)], minutos atrás)
MESAS_EM_ATENDIMENTO = [
    (2, [("Moqueca de peixe", 1, "em_preparo"), ("Suco natural", 2, "novo")], 12),
    (4, [("Feijoada completa", 1, "entregue"), ("Petit gâteau", 1, "pronto")], 35),
]
ORDEM_DOS_STATUS = ["novo", "em_preparo", "pronto", "entregue"]


def _email(membro, dominio):
    """("Júlia Martins", "garcom", "julia") -> julia@dominio; sem o 3º item, usa o perfil."""
    return f"{membro[2] if len(membro) > 2 else membro[1]}@{dominio}"


def criar_dados_demo(db, senha):
    for dados in RESTAURANTES:
        equipe, dominio = dados["equipe"], dados["dominio"]
        restaurante_id, _ = regras.cadastrar_restaurante(
            db, dados["nome"], equipe[0][0], f"gerente@{dominio}", senha
        )
        regras.mudar_plano(db, restaurante_id, dados["plano"])
        regras.configurar_taxa_servico(db, restaurante_id, dados["taxa_servico"])
        usuarios = {}  # {início do e-mail: id}
        for membro in equipe[1:]:
            email = _email(membro, dominio)
            usuarios[email.split("@")[0]] = regras.criar_usuario(
                db, restaurante_id, membro[0], email, senha, membro[1]
            )

        produtos = {}
        for categoria, itens in dados["cardapio"].items():
            categoria_id = regras.criar_categoria(db, restaurante_id, categoria)
            for nome, preco in itens:
                produtos[nome] = regras.criar_produto(db, restaurante_id, categoria_id, nome, preco)

        mesas = {n: regras.criar_mesa(db, restaurante_id, n) for n in range(1, dados["mesas"] + 1)}

        if dados is RESTAURANTES[0]:
            _criar_movimento(db, restaurante_id, usuarios, produtos, mesas)


def _criar_movimento(db, restaurante_id, usuarios, produtos, mesas):
    """Vendas de hoje e mesas em atendimento, para o painel e a cozinha não começarem vazios."""
    for numero, itens, forma, minutos, garcom in CONTAS_FECHADAS:
        pedido_id = regras.abrir_pedido(db, restaurante_id, mesas[numero], usuarios[garcom])
        for produto, quantidade in itens:
            _lancar(db, restaurante_id, pedido_id, produtos[produto], quantidade, "entregue")
        total = regras.resumo_conta(db, restaurante_id, pedido_id)["total"]
        regras.registrar_pagamento(db, restaurante_id, pedido_id, forma, total)
        _voltar_no_tempo(db, pedido_id, minutos)

    for numero, itens, minutos in MESAS_EM_ATENDIMENTO:
        pedido_id = regras.abrir_pedido(db, restaurante_id, mesas[numero], usuarios["garcom"])
        for produto, quantidade, status in itens:
            _lancar(db, restaurante_id, pedido_id, produtos[produto], quantidade, status)
        _voltar_no_tempo(db, pedido_id, minutos)


def _lancar(db, restaurante_id, pedido_id, produto_id, quantidade, status_final):
    item_id = regras.adicionar_item(db, restaurante_id, pedido_id, produto_id, quantidade)
    for passo in range(ORDEM_DOS_STATUS.index(status_final)):
        regras.avancar_item(
            db, restaurante_id, item_id, ORDEM_DOS_STATUS[passo], ORDEM_DOS_STATUS[passo + 1]
        )


def _voltar_no_tempo(db, pedido_id, minutos):
    """Recua os horários de uma comanda em alguns minutos, sem passar para o dia anterior."""
    agora = datetime.now()
    minutos = min(minutos, agora.hour * 60 + agora.minute)
    if minutos <= 0:
        return
    ajuste = f"-{minutos} minutes"
    with db:
        db.execute(
            "UPDATE pedido SET aberto_em = datetime(aberto_em, ?), fechado_em = datetime(fechado_em, ?) WHERE id = ?",
            (ajuste, ajuste, pedido_id),
        )
        db.execute(
            "UPDATE item_pedido SET criado_em = datetime(criado_em, ?), atualizado_em = datetime(atualizado_em, ?) WHERE pedido_id = ?",
            (ajuste, ajuste, pedido_id),
        )
        db.execute(
            "UPDATE pagamento SET pago_em = datetime(pago_em, ?) WHERE pedido_id = ?",
            (ajuste, pedido_id),
        )


@click.command("seed-demo")
def seed_demo_command():
    """Recria o banco com dois restaurantes de demonstração."""
    senha = os.environ.get("SENHA_DEMO") or click.prompt(
        "Senha para os usuários de demonstração", hide_input=True, confirmation_prompt=True
    )
    init_db()
    try:
        criar_dados_demo(get_db(), senha)
    except regras.RegraViolada as erro:
        raise click.ClickException(str(erro))
    click.echo("Banco recriado com os dados de demonstração.")
    for dados in RESTAURANTES:
        emails = ", ".join(_email(membro, dados["dominio"]) for membro in dados["equipe"])
        click.echo(f"  {dados['nome']}: {emails}")
    click.echo("Senha de todos: a que está em SENHA_DEMO no arquivo .env.")


def init_app(app):
    app.cli.add_command(seed_demo_command)
