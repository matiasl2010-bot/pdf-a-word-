import fitz
import pdfplumber

UMBRAL_CARACTERES = 50


def tipos_por_pagina(pdf_path: str) -> list:
    """Devuelve 'digital' o 'escaneado' por cada pagina del PDF.

    Usa pymupdf y no pdfplumber: para esta clasificacion solo hace falta saber
    cuanto texto tiene cada pagina, y pymupdf lo resuelve unas 70 veces mas
    rapido (en un PDF de 34 paginas: 0.7s contra 50s). pdfplumber se sigue
    usando para extraer texto y tablas, que es donde su precision importa."""
    tipos = []
    doc = fitz.open(pdf_path)
    try:
        for page in doc:
            texto = page.get_text() or ""
            tipos.append("digital" if len(texto.strip()) >= UMBRAL_CARACTERES else "escaneado")
    finally:
        doc.close()
    return tipos


def detectar_tipo(pdf_path: str) -> str:
    tipos = tipos_por_pagina(pdf_path)
    unicos = set(tipos)
    if unicos == {"digital"}:
        return "digital"
    if unicos == {"escaneado"}:
        return "escaneado"
    return "mixto"


def extraer_texto_y_tablas(pdf_path: str, paginas: list, on_pagina=None) -> dict:
    """paginas: indices 0-based. Devuelve {pagina: {"texto": str, "tablas": list}}.
    on_pagina(indice), si se pasa, se llama despues de procesar cada pagina
    (para reportar progreso en documentos con muchas paginas)."""
    resultado = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i in paginas:
            page = pdf.pages[i]
            resultado[i] = {
                "texto": page.extract_text() or "",
                "tablas": page.extract_tables() or [],
            }
            if on_pagina:
                on_pagina(i)
    return resultado


def renderizar_paginas(
    pdf_path: str, paginas: list, zoom: float = 1.6, formato: str = "jpeg", calidad: int = 75,
    on_pagina=None,
) -> dict:
    """Devuelve {pagina: bytes_imagen} para las paginas indicadas.

    Por defecto usa JPEG comprimido en vez de PNG: una pagina A4 en PNG puede
    pesar varios MB y, en base64, hace que la subida a la API de OCR supere el
    timeout. El JPEG es mucho mas liviano sin perder legibilidad para OCR."""
    resultado = {}
    doc = fitz.open(pdf_path)
    try:
        for i in paginas:
            page = doc[i]
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            if formato == "jpeg":
                resultado[i] = pix.tobytes("jpeg", jpg_quality=calidad)
            else:
                resultado[i] = pix.tobytes(formato)
            if on_pagina:
                on_pagina(i)
    finally:
        doc.close()
    return resultado
