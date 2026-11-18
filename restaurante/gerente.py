"""Telas do gerente: painel do dia, cardápio, mesas, equipe e plano."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from . import regras
from .auth import perfil_requerido, restaurante_id
from .db import get_db
from .util import RegraViolada, agora, data_por_extenso, escala_bonita, reais_para_centavos, saudacao

bp = Blueprint("gerente", __name__, url_prefix="/gerente")


@bp.route("/painel")
@perfil_requerido("gerente")
def painel():
    db = get_db()
    uso = regras.uso_do_plano(db, restaurante_id())
    passos = {
        "produtos": regras.contar_produtos(db, restaurante_id()),
        "mesas": uso["mesas"],
        "equipe": uso["usuarios"],
    }
    resumo = regras.resumo_do_dia(db, restaurante_id())
    horas = regras.vendas_por_hora(db, restaurante_id())
    topo, marcas = escala_bonita(max(h["valor"] for h in horas))
    # Formas de pagamento em ordem fixa (a cor acompanha a forma, não a posição no ranking)
    valores = {linha["forma"]: linha for linha in resumo["por_forma"]}
    formas = [valores[forma] for forma in ("pix", "cartao", "dinheiro") if forma in valores]
    return render_template(
        "gerente/painel.html",
        resumo=resumo,
        agora=regras.situacao_agora(db, restaurante_id()),
        horas=horas,
        topo=topo,
        marcas=marcas,
        formas=formas,
        uso=uso,
        passos=passos,
        saudacao=saudacao(),
        primeiro_nome=g.usuario["nome"].split()[0],
        data_hoje=data_por_extenso(),
        hora_atual=agora()[11:16],
    )


# ---------- Cardápio ----------

@bp.route("/cardapio")
@perfil_requerido("gerente")
def cardapio():
    grupos = regras.cardapio(get_db(), restaurante_id())
    disponiveis = sum(1 for grupo in grupos for produto in grupo["produtos"] if produto["ativo"])
    return render_template("gerente/cardapio.html", grupos=grupos, disponiveis=disponiveis)


@bp.post("/categorias")
@perfil_requerido("gerente")
def nova_categoria():
    try:
        regras.criar_categoria(get_db(), restaurante_id(), request.form.get("nome"))
        flash("Categoria criada.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
        return redirect(url_for(".cardapio", _anchor="nova-categoria"))
    return redirect(url_for(".cardapio"))


@bp.post("/produtos")
@perfil_requerido("gerente")
def novo_produto():
    try:
        produto_id = regras.criar_produto(
            get_db(),
            restaurante_id(),
            request.form.get("categoria_id", type=int),
            request.form.get("nome"),
            reais_para_centavos(request.form.get("preco")),
        )
    except RegraViolada as erro:
        flash(str(erro), "erro")
        return redirect(url_for(".cardapio", _anchor="novo-produto"))
    flash("Produto adicionado ao cardápio.", "ok")
    return redirect(url_for(".cardapio", _anchor=f"produto-{produto_id}"))


@bp.post("/produtos/<int:produto_id>")
@perfil_requerido("gerente")
def editar_produto(produto_id):
    formulario = request.form
    try:
        nome = regras.editar_produto(
            get_db(),
            restaurante_id(),
            produto_id,
            formulario.get("nome"),
            formulario.get("categoria_id", type=int),
            reais_para_centavos(formulario.get("preco")),
            ativo=formulario.get("ativo") == "sim",
        )
    except RegraViolada as erro:
        flash(str(erro), "erro")
        # Volta com a janela de edição aberta para corrigir
        return redirect(url_for(".cardapio", _anchor=f"editar-{produto_id}"))
    flash(f"{nome} atualizado. Contas já lançadas mantêm o preço antigo.", "ok")
    return redirect(url_for(".cardapio", _anchor=f"produto-{produto_id}"))


@bp.post("/produtos/<int:produto_id>/alternar")
@perfil_requerido("gerente")
def alternar_produto(produto_id):
    try:
        regras.alternar_produto(get_db(), restaurante_id(), produto_id)
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".cardapio", _anchor=f"produto-{produto_id}"))


# ---------- Mesas ----------

@bp.route("/mesas")
@perfil_requerido("gerente")
def mesas():
    db = get_db()
    mesas = regras.listar_mesas(db, restaurante_id())
    proximo_numero = max((m["numero"] for m in mesas), default=0) + 1
    return render_template(
        "gerente/mesas.html",
        mesas=mesas,
        uso=regras.uso_do_plano(db, restaurante_id()),
        proximo_numero=proximo_numero,
    )


@bp.post("/mesas")
@perfil_requerido("gerente")
def nova_mesa():
    try:
        regras.criar_mesa(get_db(), restaurante_id(), request.form.get("numero", type=int))
        flash("Mesa cadastrada.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".mesas"))


# ---------- Equipe ----------

@bp.route("/equipe")
@perfil_requerido("gerente")
def equipe():
    db = get_db()
    return render_template(
        "gerente/equipe.html",
        usuarios=regras.listar_usuarios(db, restaurante_id()),
        uso=regras.uso_do_plano(db, restaurante_id()),
    )


@bp.post("/equipe")
@perfil_requerido("gerente")
def novo_usuario():
    formulario = request.form
    try:
        regras.criar_usuario(
            get_db(),
            restaurante_id(),
            formulario.get("nome"),
            formulario.get("email"),
            formulario.get("senha"),
            formulario.get("perfil"),
        )
        flash("Usuário cadastrado. Passe o e-mail e a senha para a pessoa.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".equipe"))


@bp.post("/equipe/<int:usuario_id>/alternar")
@perfil_requerido("gerente")
def alternar_usuario(usuario_id):
    try:
        regras.alternar_usuario(get_db(), restaurante_id(), usuario_id, g.usuario["id"])
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".equipe"))


# ---------- Plano (assinatura do SaaS) ----------

@bp.route("/plano")
@perfil_requerido("gerente")
def plano():
    return render_template("gerente/plano.html", uso=regras.uso_do_plano(get_db(), restaurante_id()))


@bp.post("/taxa-servico")
@perfil_requerido("gerente")
def configurar_taxa():
    percentual = request.form.get("percentual", type=int) if request.form.get("cobrar") == "sim" else 0
    try:
        regras.configurar_taxa_servico(get_db(), restaurante_id(), percentual)
        if percentual:
            flash(f"Taxa de serviço de {percentual}% nas próximas comandas.", "ok")
        else:
            flash("Taxa de serviço desligada para as próximas comandas.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".plano"))


@bp.post("/plano")
@perfil_requerido("gerente")
def mudar_plano():
    escolhido = request.form.get("plano")
    try:
        regras.mudar_plano(get_db(), restaurante_id(), escolhido)
        flash(f"Plano alterado para {regras.PLANOS[escolhido]['nome']}.", "ok")
    except RegraViolada as erro:
        flash(str(erro), "erro")
    return redirect(url_for(".plano"))
