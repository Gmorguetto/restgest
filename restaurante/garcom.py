"""Telas do garçom: salão (mesas), comanda, lançamento e entrega de itens."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from . import regras
from .auth import perfil_requerido, restaurante_id
from .db import get_db
from .util import RegraViolada, endereco_de_volta

bp = Blueprint("garcom", __name__, url_prefix="/garcom")


@bp.route("/mesas")
@perfil_requerido("garcom")
def mesas():
    db = get_db()
    mesas = regras.mesas_com_situacao(db, restaurante_id())
    ocupadas = sum(1 for mesa in mesas if mesa["pedido_id"])
    return render_template(
        "garcom/mesas.html",
        mesas=mesas,
        prontos=regras.itens_por_status(db, restaurante_id(), ("pronto",)),
        ocupadas=ocupadas,
        livres=len(mesas) - ocupadas,
    )


@bp.post("/mesas/<int:mesa_id>/abrir")
@perfil_requerido("garcom")
def abrir(mesa_id):
    try:
        pedido_id = regras.abrir_pedido(get_db(), restaurante_id(), mesa_id, g.usuario["id"])
    except RegraViolada as erro:
        flash(str(erro), "erro")
        return redirect(url_for(".mesas"))
    return redirect(url_for(".pedido", pedido_id=pedido_id))


@bp.route("/pedidos/<int:pedido_id>")
@perfil_requerido("garcom")
def pedido(pedido_id):
    db = get_db()
    try:
        conta = regras.resumo_conta(db, restaurante_id(), pedido_id)
    except RegraViolada:
        abort(404)  # não existe ou é de outro restaurante
    return render_template(
        "garcom/pedido.html",
        conta=conta,
        cardapio=regras.cardapio(db, restaurante_id(), so_ativos=True),
    )


@bp.post("/pedidos/<int:pedido_id>/itens")
@perfil_requerido("garcom")
def adicionar_item(pedido_id):
    try:
        regras.adicionar_item(
            get_db(),
            restaurante_id(),
            pedido_id,
            request.form.get("produto_id", type=int),
            request.form.get("quantidade", type=int),
            request.form.get("observacao", ""),
        )
        flash("Item enviado para a cozinha.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".pedido", pedido_id=pedido_id))


@bp.post("/pedidos/<int:pedido_id>/cancelar")
@perfil_requerido("garcom")
def cancelar_pedido(pedido_id):
    try:
        numero = regras.cancelar_pedido(get_db(), restaurante_id(), pedido_id)
        flash(f"Comanda cancelada. A mesa {numero} está livre.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
        return redirect(url_for(".pedido", pedido_id=pedido_id))
    return redirect(url_for(".mesas"))


@bp.post("/itens/<int:item_id>/entregar")
@perfil_requerido("garcom")
def entregar(item_id):
    try:
        regras.avancar_item(get_db(), restaurante_id(), item_id, "pronto", "entregue")
        flash("Item marcado como entregue.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(endereco_de_volta(url_for(".mesas")))


@bp.post("/itens/<int:item_id>/cancelar")
@perfil_requerido("garcom")
def cancelar_item(item_id):
    try:
        regras.cancelar_item(get_db(), restaurante_id(), item_id)
        flash("Item cancelado.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(endereco_de_volta(url_for(".mesas")))
