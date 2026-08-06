"""Convierte el texto extraido (OCR o pdfplumber) a Markdown sin pasar por un LLM.

Es el camino por defecto porque garantiza que no se pierda contenido: un modelo
de lenguaje, por mas que se le pida transcribir, omite fragmentos de forma
impredecible. Aca el texto se copia tal cual y solo se infiere el formato
(titulos, listas, tablas) con reglas simples.
"""

import re

SIMBOLOS_LISTA = ("- ", "* ", "• ", "· ", "◦ ")

# "1. Titulo", "2.3 Subtitulo", "IV. Seccion"
RE_TITULO_NUMERADO = re.compile(r"^(\d+(\.\d+)*\.?|[IVXLC]+\.)\s+\S")

LARGO_MAX_TITULO = 80


def _es_titulo_mayusculas(linea: str) -> bool:
    if len(linea) > LARGO_MAX_TITULO:
        return False
    letras = [c for c in linea if c.isalpha()]
    if len(letras) < 3:
        return False
    return all(c.isupper() for c in letras)


def _convertir_linea(linea: str) -> str:
    despojada = linea.strip()
    if not despojada:
        return ""

    for simbolo in SIMBOLOS_LISTA:
        if despojada.startswith(simbolo):
            return "- " + despojada[len(simbolo):].strip()

    if _es_titulo_mayusculas(despojada):
        return f"# {despojada}"

    if RE_TITULO_NUMERADO.match(despojada) and len(despojada) <= LARGO_MAX_TITULO:
        return f"## {despojada}"

    return despojada


def _tabla_a_markdown(tabla: list) -> str:
    if not tabla:
        return ""

    def celda(c):
        return str(c).replace("\n", " ").strip() if c is not None else ""

    filas = [[celda(c) for c in fila] for fila in tabla]
    n_cols = max(len(f) for f in filas)
    filas = [f + [""] * (n_cols - len(f)) for f in filas]

    lineas = ["| " + " | ".join(filas[0]) + " |"]
    lineas.append("| " + " | ".join(["---"] * n_cols) + " |")
    for fila in filas[1:]:
        lineas.append("| " + " | ".join(fila) + " |")
    return "\n".join(lineas)


def convertir(paginas: list) -> str:
    """paginas: lista de {"texto": str, "tablas": list}, en orden de documento."""
    partes = []

    for pagina in paginas:
        texto = pagina.get("texto", "") or ""
        lineas_md = [_convertir_linea(l) for l in texto.split("\n")]
        cuerpo = "\n".join(lineas_md).strip()
        if cuerpo:
            partes.append(cuerpo)

        for tabla in pagina.get("tablas", []) or []:
            md_tabla = _tabla_a_markdown(tabla)
            if md_tabla:
                partes.append(md_tabla)

    return "\n\n".join(partes)
