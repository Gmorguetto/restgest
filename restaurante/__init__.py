"""Fábrica da aplicação Flask.

Camadas do sistema:
* Interface: templates/ (páginas HTML geradas no servidor) e static/estilo.css
* Lógica da aplicação: rotas em auth.py, gerente.py, garcom.py, cozinha.py,
  caixa.py e regras de negócio em regras.py
* Armazenamento: db.py e schema.sql (banco SQLite)
"""
import os
import secrets
from datetime import datetime

from flask import Flask, abort, g, redirect, render_template, request, session, url_for

from . import auth, caixa, cozinha, dados_demo, db, garcom, gerente, regras, util


def create_app(config_teste=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        # Segredos vêm do arquivo .env (que não vai para o GitHub), nunca do código.
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE=os.path.join(app.instance_path, "restaurante.db"),
        NOME_SISTEMA=os.environ.get("NOME_SISTEMA", "RestGest"),
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config_teste:
        app.config.update(config_teste)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        app.logger.warning(
            "SECRET_KEY não definida no .env: usando uma chave temporária "
            "(todos saem do sistema quando o servidor reinicia)."
        )
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    if os.path.exists(app.config["DATABASE"]):
        with app.app_context():
            db.atualizar_banco()
    dados_demo.init_app(app)
    for modulo in (auth, gerente, garcom, cozinha, caixa):
        app.register_blueprint(modulo.bp)

    # Filtros e valores disponíveis em todos os templates
    app.jinja_env.filters.update(
        moeda=util.centavos_para_reais,
        moeda_curta=util.centavos_para_reais_curto,
        urgencia=util.urgencia,
        plural=util.plural,
        figura_categoria=util.figura_categoria,
        campo_moeda=util.centavos_para_campo,
        hora=util.hora,
        data=util.data_br,
        tempo_espera=util.tempo_espera,
        minutos_desde=util.minutos_desde,
    )
    app.jinja_env.globals.update(
        csrf_token=_token_csrf,
        nome_sistema=app.config["NOME_SISTEMA"],
        perfis=regras.PERFIS,
        status_item=regras.STATUS_ITEM,
        formas_pagamento=regras.FORMAS_PAGAMENTO,
        planos=regras.PLANOS,
        implantacao=regras.IMPLANTACAO,
        incluso_na_mensalidade=regras.INCLUSO_NA_MENSALIDADE,
        fora_do_escopo=regras.FORA_DO_ESCOPO,
    )

    @app.context_processor
    def versao_dos_arquivos_estaticos():
        # Muda quando o CSS ou o JS mudam, para o navegador não usar a versão antiga guardada
        pasta = app.static_folder
        datas = [os.path.getmtime(os.path.join(pasta, nome)) for nome in ("estilo.css", "app.js")]
        return {"versao_estatica": int(max(datas)), "ano_atual": datetime.now().year}

    app.before_request(_verificar_csrf)
    for codigo in (400, 403, 404, 405):
        app.register_error_handler(codigo, _pagina_de_erro)
    return app


# ---------- Proteção contra CSRF ----------
# Todo formulário leva um código secreto guardado na sessão do usuário.
# Um site malicioso não conhece esse código, então não consegue enviar
# formulários em nome de quem está logado.

def _token_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def _verificar_csrf():
    if request.method != "POST":
        return None
    esperado = session.get("csrf_token")
    recebido = request.form.get("csrf_token", "")
    if esperado and secrets.compare_digest(esperado, recebido):
        return None
    if request.endpoint == "auth.login" and g.get("usuario"):
        # Clique duplo em "Entrar": o primeiro envio já fez o login
        return redirect(url_for("auth.inicio"))
    abort(400, "O formulário expirou. Volte, recarregue a página e tente de novo.")


MENSAGENS_DE_ERRO = {
    403: ("Acesso negado", "O seu perfil não tem acesso a esta página."),
    404: ("Página não encontrada", "Não encontramos o que você procurou."),
    405: ("Ação não permitida", "Esta ação não pode ser feita desse jeito."),
}


def _pagina_de_erro(erro):
    if erro.code == 400:
        titulo, mensagem = "Não foi possível concluir", erro.description
    else:
        titulo, mensagem = MENSAGENS_DE_ERRO[erro.code]
    return render_template("erro.html", titulo=titulo, mensagem=mensagem), erro.code
