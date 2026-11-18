"""Camada de armazenamento: conexão com o banco SQLite.

Cada requisição abre uma conexão (get_db) e a fecha no final (close_db).
"""
import sqlite3

import click
from flask import current_app, g


def get_db():
    """Devolve a conexão com o banco da requisição atual, abrindo se preciso."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row  # permite ler colunas pelo nome: linha["nome"]
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(erro=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Apaga e recria todas as tabelas a partir do schema.sql."""
    db = get_db()
    with current_app.open_resource("schema.sql") as arquivo:
        db.executescript(arquivo.read().decode("utf-8"))


def _colunas(db, tabela):
    return {linha["name"] for linha in db.execute(f"PRAGMA table_info({tabela})")}


def atualizar_banco():
    """Migração: acrescenta as colunas novas a um banco criado por uma versão
    anterior do sistema, sem apagar nenhum dado. Pode rodar várias vezes."""
    db = get_db()
    if not _colunas(db, "restaurante"):
        return  # banco ainda vazio: o init-db cria tudo
    with db:
        if "taxa_servico" not in _colunas(db, "restaurante"):
            db.execute(
                "ALTER TABLE restaurante ADD COLUMN taxa_servico INTEGER NOT NULL DEFAULT 10 "
                "CHECK (taxa_servico BETWEEN 0 AND 20)"
            )
        if "taxa_servico" not in _colunas(db, "pedido"):
            db.execute(
                "ALTER TABLE pedido ADD COLUMN taxa_servico INTEGER NOT NULL DEFAULT 0 "
                "CHECK (taxa_servico BETWEEN 0 AND 20)"
            )
            # Comandas abertas passam a ter a taxa do restaurante; as fechadas ficam como foram pagas
            db.execute(
                """UPDATE pedido SET taxa_servico =
                     (SELECT r.taxa_servico FROM restaurante r WHERE r.id = pedido.restaurante_id)
                   WHERE status = 'aberto'"""
            )


@click.command("init-db")
def init_db_command():
    """Cria o banco de dados vazio (apaga o que existir)."""
    init_db()
    click.echo("Banco de dados criado (vazio).")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
