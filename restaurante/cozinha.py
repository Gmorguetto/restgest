"""Tela da cozinha: comandas por mesa, em três colunas (novos, em preparo, prontos)."""
from flask import Blueprint, flash, redirect, render_template, url_for

from . import regras
from .auth import perfil_requerido, restaurante_id
from .db import get_db
from .util import RegraViolada, agora

bp = Blueprint("cozinha", __name__, url_prefix="/cozinha")


@bp.route("/")
@perfil_requerido("cozinha")
def fila():
    comandas = regras.comandas_da_cozinha(get_db(), restaurante_id())
    em_espera = comandas["novo"] + comandas["em_preparo"]
    mais_antiga = max(em_espera, key=lambda c: c["minutos"]) if em_espera else None
    return render_template(
        "cozinha/fila.html",
        comandas=comandas,
        contagem={situacao: sum(len(c["itens"]) for c in lista) for situacao, lista in comandas.items()},
        mais_antiga=mais_antiga,
        hora_atual=agora()[11:16],
    )


def _voltar(acao):
    try:
        acao()
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".fila"))


# Um item por vez
@bp.post("/itens/<int:item_id>/iniciar")
@perfil_requerido("cozinha")
def iniciar(item_id):
    return _voltar(lambda: regras.avancar_item(get_db(), restaurante_id(), item_id, "novo", "em_preparo"))


@bp.post("/itens/<int:item_id>/pronto")
@perfil_requerido("cozinha")
def pronto(item_id):
    return _voltar(lambda: regras.avancar_item(get_db(), restaurante_id(), item_id, "em_preparo", "pronto"))


# A comanda inteira de uma vez
@bp.post("/pedidos/<int:pedido_id>/iniciar")
@perfil_requerido("cozinha")
def iniciar_comanda(pedido_id):
    return _voltar(lambda: regras.avancar_itens_do_pedido(get_db(), restaurante_id(), pedido_id, "novo", "em_preparo"))


@bp.post("/pedidos/<int:pedido_id>/pronto")
@perfil_requerido("cozinha")
def pronto_comanda(pedido_id):
    return _voltar(lambda: regras.avancar_itens_do_pedido(get_db(), restaurante_id(), pedido_id, "em_preparo", "pronto"))
