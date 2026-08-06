"""Saca de la salida del OCR lo que dice el modelo y no el documento.

Los modelos de vision suelen envolver la transcripcion en frases de cortesia
("¡Claro que sí! El texto de la imagen es el siguiente:"), agregar notas al pie
("Nota: el texto está en español") o describir la imagen en vez de transcribirla.
Todo eso termina como contenido en el .docx si no se filtra.
"""

import re

# Lineas que son comentario del modelo, no contenido del documento.
PATRONES_RUIDO = (
    r"^(¡?claro( que s[ií])?!?|por supuesto|entendido|aqu[ií] (tienes|est[aá])).{0,60}$",
    r"^.{0,40}\b(el )?texto (de|en) la imagen es( el siguiente)?:?\s*$",
    r"^.{0,40}\btranscri(pci[oó]n|to|bo|pto)\b.{0,40}:\s*$",
    r"^.{0,30}\bla imagen (muestra|contiene|presenta|parece)\b.*$",
    r"^.{0,30}\bno (hay|se (ve|observa)|contiene)\b.*\btexto\b.*$",
    r"^nota:.*$",
    r"^.{0,30}\best[aá] (escrito|redactado) en (espa[nñ]ol|ingl[eé]s)\b.*$",
    r"^```.*$",
)
RE_RUIDO = [re.compile(p, re.IGNORECASE) for p in PATRONES_RUIDO]

RE_VINETA = re.compile(r"^\s*[\*\-•·]\s+")


def _es_ruido(linea: str) -> bool:
    despojada = linea.strip()
    if not despojada:
        return False
    return any(r.match(despojada) for r in RE_RUIDO)


def _sacar_vinetas_globales(lineas: list) -> list:
    """Si TODAS las lineas con contenido empiezan con vineta, el modelo las
    invento: el documento no era una lista entera. Si solo algunas la tienen,
    es una lista real y se respeta."""
    con_texto = [l for l in lineas if l.strip()]
    if len(con_texto) < 2:
        return lineas
    if not all(RE_VINETA.match(l) for l in con_texto):
        return lineas
    return [RE_VINETA.sub("", l) if l.strip() else l for l in lineas]


def limpiar(texto: str) -> str:
    if not texto:
        return ""

    lineas = [l for l in texto.split("\n") if not _es_ruido(l)]
    lineas = _sacar_vinetas_globales(lineas)

    # colapsar los saltos que quedaron al sacar lineas
    resultado = "\n".join(lineas)
    resultado = re.sub(r"\n{3,}", "\n\n", resultado)
    return resultado.strip("\n")
