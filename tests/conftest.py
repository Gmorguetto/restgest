"""Preparação dos testes: cada teste recebe um banco novo com os dados de demonstração.

A senha dos usuários de teste é sorteada a cada execução, então nenhuma
senha fica escrita no código.
"""
import secrets
import shutil

import pytest

from restaurante import create_app
from restaurante.dados_demo import criar_dados_demo
from restaurante.db import get_db, init_db

SENHA = secrets.token_urlsafe(12)
SABOR = "Restaurante Sabor da Casa"
LANCHONETE = "Lanchonete do Bairro"


@pytest.fixture(scope="session")
def banco_modelo(tmp_path_factory):
    """Cria o banco de demonstração uma vez; cada teste trabalha numa cópia."""
    caminho = tmp_path_factory.mktemp("modelo") / "modelo.db"
    app = create_app({"TESTING": True, "DATABASE": str(caminho), "SECRET_KEY": secrets.token_hex(16)})
    with app.app_context():
        init_db()
        criar_dados_demo(get_db(), SENHA)
    return caminho


@pytest.fixture
def app(banco_modelo, tmp_path):
    caminho = tmp_path / "teste.db"
    shutil.copy(banco_modelo, caminho)
    return create_app({"TESTING": True, "DATABASE": str(caminho), "SECRET_KEY": secrets.token_hex(16)})


@pytest.fixture
def db(app):
    """Conexão direta com o banco, para testar as regras sem passar pelas telas."""
    with app.app_context():
        yield get_db()


class Navegador:
    """Um navegador de teste que envia o token CSRF junto com os formulários."""

    def __init__(self, app):
        self.client = app.test_client()

    def get(self, url, **kwargs):
        return self.client.get(url, **kwargs)

    def post(self, url, dados=None, **kwargs):
        with self.client.session_transaction() as sessao:
            token = sessao.setdefault("csrf_token", secrets.token_urlsafe(16))
        return self.client.post(url, data={**(dados or {}), "csrf_token": token}, **kwargs)

    def texto(self, url):
        return self.get(url, follow_redirects=True).get_data(as_text=True)


@pytest.fixture
def entrar(app):
    """entrar("garcom@sabordacasa.demo") devolve um navegador já logado."""
    def _entrar(email, senha=SENHA):
        navegador = Navegador(app)
        resposta = navegador.post("/login", {"email": email, "senha": senha})
        assert resposta.status_code == 302, f"login de {email} falhou"
        return navegador
    return _entrar


@pytest.fixture
def visitante(app):
    return Navegador(app)


def consultar(app, sql, parametros=()):
    """Lê o banco fora de uma requisição (para conferir o que as telas gravaram)."""
    with app.app_context():
        return get_db().execute(sql, parametros).fetchall()


def id_restaurante(db, nome):
    return db.execute("SELECT id FROM restaurante WHERE nome = ?", (nome,)).fetchone()["id"]


def id_mesa(db, restaurante_id, numero):
    return db.execute(
        "SELECT id FROM mesa WHERE restaurante_id = ? AND numero = ?", (restaurante_id, numero)
    ).fetchone()["id"]


def id_produto(db, restaurante_id, nome):
    return db.execute(
        "SELECT id FROM produto WHERE restaurante_id = ? AND nome = ?", (restaurante_id, nome)
    ).fetchone()["id"]


def id_usuario(db, email):
    return db.execute("SELECT id FROM usuario WHERE email = ?", (email,)).fetchone()["id"]
