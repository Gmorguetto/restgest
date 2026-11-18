"""Login, saída, cadastro de restaurante e controle de acesso por perfil."""
import functools

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from . import regras
from .db import get_db
from .util import RegraViolada, endereco_seguro

bp = Blueprint("auth", __name__)

# Página inicial de cada perfil depois do login
PAGINA_INICIAL = {
    "gerente": "gerente.painel",
    "garcom": "garcom.mesas",
    "cozinha": "cozinha.fila",
    "caixa": "caixa.contas",
}


@bp.before_app_request
def carregar_usuario():
    """Antes de cada requisição, carrega o usuário logado em g.usuario (ou None)."""
    g.usuario = None
    usuario_id = session.get("usuario_id")
    if usuario_id is None:
        return
    usuario = get_db().execute(
        """SELECT u.id, u.nome, u.email, u.perfil, u.restaurante_id,
                  r.nome AS restaurante_nome, r.plano
           FROM usuario u JOIN restaurante r ON r.id = u.restaurante_id
           WHERE u.id = ? AND u.ativo = 1 AND r.ativo = 1""",
        (usuario_id,),
    ).fetchone()
    if usuario is None:
        session.clear()  # usuário desativado ou apagado: sai do sistema
    else:
        g.usuario = usuario


def restaurante_id():
    """O restaurante do usuário logado. Toda consulta usa este valor."""
    return g.usuario["restaurante_id"]


def perfil_requerido(*perfis):
    """Decorador: exige login e um dos perfis informados. O gerente acessa tudo."""
    def decorador(view):
        @functools.wraps(view)
        def protegida(**kwargs):
            if g.usuario is None:
                return redirect(url_for("auth.login", proximo=request.path))
            if g.usuario["perfil"] != "gerente" and g.usuario["perfil"] not in perfis:
                abort(403)
            return view(**kwargs)
        return protegida
    return decorador


def _entrar(usuario_id):
    session.clear()  # nova sessão a cada login
    session["usuario_id"] = usuario_id


@bp.route("/")
def inicio():
    if g.usuario:
        return redirect(url_for(PAGINA_INICIAL[g.usuario["perfil"]]))
    return render_template("inicio.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        try:
            usuario = regras.autenticar(get_db(), request.form.get("email"), request.form.get("senha"))
        except RegraViolada as erro:
            flash(str(erro), "erro")
        else:
            _entrar(usuario["id"])
            return redirect(endereco_seguro(request.args.get("proximo"), url_for("auth.inicio")))
    usuarios_demo = {}  # {nome do restaurante: [usuários]}
    for usuario in regras.usuarios_de_demonstracao(get_db()):
        usuarios_demo.setdefault(usuario["restaurante"], []).append(usuario)
    return render_template("auth/login.html", usuarios_demo=usuarios_demo)


@bp.post("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/cadastro", methods=("GET", "POST"))
def cadastro():
    """Onboarding do SaaS: o dono cria o restaurante e já entra como gerente."""
    if request.method == "POST":
        formulario = request.form
        try:
            if formulario.get("senha") != formulario.get("confirmacao"):
                raise RegraViolada("As senhas digitadas não são iguais.")
            _, gerente_id = regras.cadastrar_restaurante(
                get_db(),
                formulario.get("restaurante"),
                formulario.get("nome"),
                formulario.get("email"),
                formulario.get("senha"),
            )
        except RegraViolada as erro:
            flash(str(erro), "erro")
        else:
            _entrar(gerente_id)
            flash(
                f"Restaurante criado! Você tem {regras.DIAS_DE_TESTE} dias de teste grátis. "
                "Comece pelo cardápio e pelas mesas.",
                "ok",
            )
            return redirect(url_for("gerente.painel"))
    return render_template("auth/cadastro.html")
