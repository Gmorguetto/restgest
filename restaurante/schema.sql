-- Estrutura do banco de dados (SQLite).
-- Rodar este arquivo apaga e recria todas as tabelas.
--
-- Regras gerais:
-- * Toda tabela que pertence a um restaurante tem restaurante_id.
--   É isso que separa os dados de cada cliente do SaaS.
-- * Dinheiro é guardado em centavos (INTEGER) para evitar erros de
--   arredondamento: R$ 12,50 vira 1250.
-- * Datas são texto no formato 'AAAA-MM-DD HH:MM:SS', no horário local.

DROP TABLE IF EXISTS pagamento;
DROP TABLE IF EXISTS item_pedido;
DROP TABLE IF EXISTS pedido;
DROP TABLE IF EXISTS mesa;
DROP TABLE IF EXISTS produto;
DROP TABLE IF EXISTS categoria;
DROP TABLE IF EXISTS usuario;
DROP TABLE IF EXISTS restaurante;

-- Cada cliente do SaaS é uma linha desta tabela.
CREATE TABLE restaurante (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    plano       TEXT    NOT NULL DEFAULT 'teste'
                CHECK (plano IN ('teste', 'basico', 'profissional')),
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT    NOT NULL,
    teste_ate   TEXT,                   -- último dia do teste grátis
    -- % de taxa de serviço cobrado nas comandas novas (0 = não cobra)
    taxa_servico INTEGER NOT NULL DEFAULT 10 CHECK (taxa_servico BETWEEN 0 AND 20)
);

-- A senha nunca é guardada: só o hash dela (senha_hash).
CREATE TABLE usuario (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurante_id  INTEGER NOT NULL REFERENCES restaurante (id),
    nome            TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    senha_hash      TEXT    NOT NULL,
    perfil          TEXT    NOT NULL
                    CHECK (perfil IN ('gerente', 'garcom', 'cozinha', 'caixa')),
    ativo           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE categoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurante_id  INTEGER NOT NULL REFERENCES restaurante (id),
    nome            TEXT    NOT NULL,
    UNIQUE (restaurante_id, nome)
);

CREATE TABLE produto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurante_id  INTEGER NOT NULL REFERENCES restaurante (id),
    categoria_id    INTEGER NOT NULL REFERENCES categoria (id),
    nome            TEXT    NOT NULL,
    preco_centavos  INTEGER NOT NULL CHECK (preco_centavos > 0),
    ativo           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE mesa (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurante_id  INTEGER NOT NULL REFERENCES restaurante (id),
    numero          INTEGER NOT NULL CHECK (numero > 0),
    status          TEXT    NOT NULL DEFAULT 'livre'
                    CHECK (status IN ('livre', 'ocupada')),
    UNIQUE (restaurante_id, numero)
);

-- A comanda de uma mesa.
CREATE TABLE pedido (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurante_id  INTEGER NOT NULL REFERENCES restaurante (id),
    mesa_id         INTEGER NOT NULL REFERENCES mesa (id),
    garcom_id       INTEGER NOT NULL REFERENCES usuario (id),
    status          TEXT    NOT NULL DEFAULT 'aberto'
                    CHECK (status IN ('aberto', 'fechado', 'cancelado')),
    aberto_em       TEXT    NOT NULL,
    fechado_em      TEXT,
    -- % de taxa de serviço desta comanda: vem do restaurante quando a mesa
    -- é aberta e o caixa pode retirar (é opcional para o cliente)
    taxa_servico    INTEGER NOT NULL DEFAULT 0 CHECK (taxa_servico BETWEEN 0 AND 20)
);

-- Garante no próprio banco que uma mesa nunca tem duas comandas abertas,
-- mesmo que dois garçons cliquem em "Abrir" no mesmo instante.
CREATE UNIQUE INDEX um_pedido_aberto_por_mesa
    ON pedido (mesa_id) WHERE status = 'aberto';

-- preco_unitario_centavos guarda o preço do momento da venda:
-- se o gerente mudar o preço depois, a conta não muda.
CREATE TABLE item_pedido (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id                INTEGER NOT NULL REFERENCES pedido (id),
    produto_id               INTEGER NOT NULL REFERENCES produto (id),
    quantidade               INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario_centavos  INTEGER NOT NULL CHECK (preco_unitario_centavos > 0),
    observacao               TEXT    NOT NULL DEFAULT '',
    status                   TEXT    NOT NULL DEFAULT 'novo'
                             CHECK (status IN ('novo', 'em_preparo', 'pronto', 'entregue', 'cancelado')),
    criado_em                TEXT    NOT NULL,
    atualizado_em            TEXT    NOT NULL
);

-- Uma conta pode ter vários pagamentos (conta dividida).
CREATE TABLE pagamento (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id       INTEGER NOT NULL REFERENCES pedido (id),
    forma           TEXT    NOT NULL CHECK (forma IN ('dinheiro', 'cartao', 'pix')),
    valor_centavos  INTEGER NOT NULL CHECK (valor_centavos > 0),
    pago_em         TEXT    NOT NULL
);

CREATE INDEX idx_pedido_restaurante ON pedido (restaurante_id, status);
CREATE INDEX idx_item_pedido ON item_pedido (pedido_id, status);
CREATE INDEX idx_pagamento_pedido ON pagamento (pedido_id);
