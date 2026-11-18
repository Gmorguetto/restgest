"""Funções auxiliares: dinheiro, datas e redirecionamento seguro.

Dinheiro é guardado em centavos (números inteiros) para evitar erros de
arredondamento de números decimais: em ponto flutuante, 0.1 + 0.2 não dá
exatamente 0.3.
"""
import math
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import request


class RegraViolada(Exception):
    """Erro de regra de negócio. A mensagem é mostrada ao usuario."""


# ---------- Dinheiro ----------

def reais_para_centavos(texto):
    """Converte o que o usuario digitou ('12,50', '12.50', 'R$ 1.234,56') em centavos."""
    limpo = (texto or "").replace("R$", "").replace(" ", "").strip()
    if "," in limpo:
        # formato brasileiro: ponto separa milhar e vírgula separa centavos
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(limpo)
    except InvalidOperation:
        raise RegraViolada(f"Valor inválido: '{texto}'. Use, por exemplo, 12,50.")
    if not valor.is_finite() or valor <= 0:
        raise RegraViolada("O valor precisa ser maior que zero.")
    if valor > 1_000_000:
        raise RegraViolada("Valor alto demais.")
    if valor != valor.quantize(Decimal("0.01")):
        raise RegraViolada("Use no máximo duas casas decimais.")
    return int(valor * 100)


def centavos_para_reais(centavos):
    """1234567 -> 'R$ 12.345,67'"""
    centavos = int(centavos or 0)
    sinal = "-" if centavos < 0 else ""
    reais, resto = divmod(abs(centavos), 100)
    return f"{sinal}R$ {reais:,}".replace(",", ".") + f",{resto:02d}"


def centavos_para_reais_curto(centavos):
    """150000 -> 'R$ 1.500' (sem centavos, para eixos de gráfico)."""
    centavos = int(centavos or 0)
    if centavos % 100:
        return centavos_para_reais(centavos)
    return f"R$ {centavos // 100:,}".replace(",", ".")


def escala_bonita(maximo, divisoes=4):
    """Topo e marcas 'redondas' para o eixo de um gráfico (valores em centavos).
    Ex.: máximo R$ 130 -> topo R$ 150 e marcas 0, 50, 100, 150."""
    if not maximo or maximo <= 0:
        maximo = 10000
    bruto = maximo / divisoes
    potencia = 10 ** math.floor(math.log10(bruto))
    for fator in (1, 2, 5, 10):
        passo = fator * potencia
        if passo >= bruto:
            break
    quantidade = math.ceil(maximo / passo)
    return int(quantidade * passo), [int(passo * i) for i in range(quantidade + 1)]


def centavos_para_campo(centavos):
    """1250 -> '12,50' (para preencher campos de formulário)."""
    centavos = int(centavos or 0)
    return f"{centavos // 100},{centavos % 100:02d}"


def chave_alfabetica(texto):
    """'Água' -> 'agua': para ordenar nomes com acento na posição certa."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()


# ---------- Datas ----------

def agora():
    """Data e hora local, ex.: '2026-11-18 20:15:03'."""
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def hoje():
    """Data local, ex.: '2026-11-18'."""
    return date.today().isoformat()


def hora(texto_iso):
    """'2026-11-18 20:15:03' -> '20:15'"""
    return (texto_iso or "")[11:16]


def data_br(texto_iso):
    """'2026-11-18' -> '18/11/2026'"""
    texto_iso = texto_iso or ""
    return f"{texto_iso[8:10]}/{texto_iso[5:7]}/{texto_iso[0:4]}"


DIAS_DA_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]


def data_por_extenso(dia=None):
    """date(2026, 11, 17) -> 'terça-feira, 17 de novembro'"""
    dia = dia or date.today()
    return f"{DIAS_DA_SEMANA[dia.weekday()]}, {dia.day} de {MESES[dia.month - 1]}"


def saudacao(hora=None):
    hora = datetime.now().hour if hora is None else hora
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def plural(quantidade, singular, plural):
    """plural(1, 'conta', 'contas') -> '1 conta'; plural(3, ...) -> '3 contas'."""
    return f"{quantidade} {singular if quantidade == 1 else plural}"


# Figurinha de cada categoria do cardápio, escolhida por palavras do nome
FIGURAS_DE_CATEGORIA = [
    ("bebida", ("bebida", "suco", "drink", "refrigerante", "cerveja", "vinho", "agua", "chopp")),
    ("cafe", ("cafe", "cafeteria", "cha")),
    ("sobremesa", ("sobremesa", "doce", "bolo", "torta", "sorvete")),
    ("lanche", ("lanche", "hamburguer", "burger", "sanduiche")),
    ("pizza", ("pizza",)),
    ("porcao", ("porcao", "porcoes", "petisco", "entrada", "aperitivo", "tira-gosto")),
]


def figura_categoria(nome):
    """'Bebidas' -> 'bebida'; 'Sobremesas' -> 'sobremesa'; nome sem pista -> 'prato'."""
    palavras = re.findall(r"[a-z]+", chave_alfabetica(nome or ""))
    for figura, pistas in FIGURAS_DE_CATEGORIA:
        for pista in pistas:
            # palavras curtas (como "cha") só valem inteiras; as outras valem no começo ("bebidas")
            if any(p == pista or (len(pista) >= 4 and p.startswith(pista)) for p in palavras):
                return figura
    return "prato"


def urgencia(minutos, atencao=10, atrasado=20):
    """Classe de cor pelo tempo de espera: 'ok', 'atencao' ou 'atrasado'."""
    if minutos >= atrasado:
        return "atrasado"
    if minutos >= atencao:
        return "atencao"
    return "ok"


def minutos_desde(texto_iso):
    instante = datetime.fromisoformat(texto_iso)
    return max(int((datetime.now() - instante).total_seconds() // 60), 0)


def tempo_espera(texto_iso):
    """Texto amigável para a cozinha: 'agora', 'há 7 min', 'há 1 h 05 min'."""
    minutos = minutos_desde(texto_iso)
    if minutos < 1:
        return "agora"
    if minutos < 60:
        return f"há {minutos} min"
    horas, resto = divmod(minutos, 60)
    return f"há {horas} h {resto:02d} min"


# ---------- Navegação ----------

def endereco_seguro(destino, padrao):
    """Só aceita endereços internos do sistema (evita redirecionar para outro site)."""
    destino = destino or ""
    if destino.startswith("/") and not destino.startswith(("//", "/\\")):
        return destino
    return padrao


def endereco_de_volta(padrao):
    """Para onde voltar depois de um formulário (campo oculto 'voltar')."""
    return endereco_seguro(request.form.get("voltar"), padrao)
