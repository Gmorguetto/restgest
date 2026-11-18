"""Telas do caixa: contas abertas, fechamento e pagamento."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import regras
from .auth import perfil_requerido, restaurante_id
from .db import get_db
from .util import RegraViolada, centavos_para_reais, reais_para_centavos

bp = Blueprint("caixa", __name__, url_prefix="/caixa")


@bp.route("/")
@perfil_requerido("caixa")
def contas():
    return render_template("caixa/contas.html", contas=regras.contas_abertas(get_db(), restaurante_id()))


@bp.route("/pedidos/<int:pedido_id>")
@perfil_requerido("caixa")
def conta(pedido_id):
    try:
        resumo = regras.resumo_conta(get_db(), restaurante_id(), pedido_id)
    except RegraViolada:
        abort(404)  # não existe ou é de outro restaurante
    return render_template(
        "caixa/conta.html",
        conta=resumo,
        taxa_restaurante=regras.uso_do_plano(get_db(), restaurante_id())["taxa_servico"],
    )


@bp.post("/pedidos/<int:pedido_id>/taxa")
@perfil_requerido("caixa")
def definir_taxa(pedido_id):
    cobrar = request.form.get("acao") == "incluir"
    try:
        percentual = regras.definir_taxa_servico(get_db(), restaurante_id(), pedido_id, cobrar)
        if percentual:
            flash(f"Taxa de serviço de {percentual}% incluída na conta.", "ok")
        else:
            flash("Taxa de serviço retirada desta conta.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".conta", pedido_id=pedido_id))


@bp.post("/pedidos/<int:pedido_id>/pagamentos")
@perfil_requerido("caixa")
def registrar_pagamento(pedido_id):
    try:
        resultado = regras.registrar_pagamento(
            get_db(),
            restaurante_id(),
            pedido_id,
            request.form.get("forma"),
            reais_para_centavos(request.form.get("valor")),
        )
    except RegraViolada as erro:
        flash(str(erro), "erro")
        return redirect(url_for(".conta", pedido_id=pedido_id))

    if resultado["fechou"]:
        mensagem = f"Conta da mesa {resultado['mesa_numero']} fechada. A mesa está livre."
        if resultado["troco"]:
            mensagem += f" Troco: {centavos_para_reais(resultado['troco'])}."
        flash(mensagem, "ok")
        return redirect(url_for(".contas"))
    flash(
        f"Pagamento registrado. Falta receber {centavos_para_reais(resultado['restante'])}.", "ok"
    )
    return redirect(url_for(".conta", pedido_id=pedido_id))
