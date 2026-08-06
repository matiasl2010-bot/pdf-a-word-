import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fitz
import pdf_analyzer

TEXTO_LARGO = "Este es un texto de prueba con suficiente longitud para superar el umbral de deteccion de pagina digital."


def _crear_pdf(path, paginas_con_texto):
    """paginas_con_texto: lista de str o None (None = pagina en blanco)."""
    doc = fitz.open()
    for texto in paginas_con_texto:
        page = doc.new_page()
        if texto:
            page.insert_text((72, 72), texto)
    doc.save(str(path))
    doc.close()


def test_tipos_por_pagina_pdf_digital(tmp_path):
    ruta = tmp_path / "digital.pdf"
    _crear_pdf(ruta, [TEXTO_LARGO])

    assert pdf_analyzer.tipos_por_pagina(str(ruta)) == ["digital"]


def test_tipos_por_pagina_pdf_escaneado(tmp_path):
    ruta = tmp_path / "escaneado.pdf"
    _crear_pdf(ruta, [None])

    assert pdf_analyzer.tipos_por_pagina(str(ruta)) == ["escaneado"]


def test_detectar_tipo_mixto(tmp_path):
    ruta = tmp_path / "mixto.pdf"
    _crear_pdf(ruta, [TEXTO_LARGO, None])

    assert pdf_analyzer.detectar_tipo(str(ruta)) == "mixto"


def test_extraer_texto_y_tablas(tmp_path):
    ruta = tmp_path / "digital.pdf"
    _crear_pdf(ruta, [TEXTO_LARGO])

    resultado = pdf_analyzer.extraer_texto_y_tablas(str(ruta), [0])

    assert 0 in resultado
    assert "prueba" in resultado[0]["texto"]
    assert isinstance(resultado[0]["tablas"], list)


def test_extraer_texto_y_tablas_avisa_por_cada_pagina(tmp_path):
    ruta = tmp_path / "tres_paginas.pdf"
    _crear_pdf(ruta, [TEXTO_LARGO, TEXTO_LARGO, TEXTO_LARGO])
    paginas_avisadas = []

    pdf_analyzer.extraer_texto_y_tablas(str(ruta), [0, 1, 2], on_pagina=paginas_avisadas.append)

    assert paginas_avisadas == [0, 1, 2]


def test_renderizar_paginas_devuelve_jpeg(tmp_path):
    ruta = tmp_path / "escaneado.pdf"
    _crear_pdf(ruta, [None])

    resultado = pdf_analyzer.renderizar_paginas(str(ruta), [0])

    assert 0 in resultado
    # JPEG empieza con el marcador SOI 0xFFD8
    assert resultado[0].startswith(b"\xff\xd8")


def _crear_pdf_escaneado_simulado(path):
    """PDF con una imagen ruidosa embebida, que es como se ve un escaneo real
    (a diferencia de texto sintetico sobre blanco puro, que PNG comprime casi perfecto)."""
    from PIL import Image

    ancho, alto = 600, 800
    img = Image.new("RGB", (ancho, alto))
    pixeles = img.load()
    for y in range(alto):
        for x in range(ancho):
            # patron determinista tipo ruido/gradiente, sin aleatoriedad
            v = (x * 7 + y * 13 + (x * y) % 97) % 256
            pixeles[x, y] = (v, (v * 3) % 256, (v * 5) % 256)
    img_path = str(path) + ".png"
    img.save(img_path)

    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(fitz.Rect(0, 0, ancho, alto), filename=img_path)
    doc.save(str(path))
    doc.close()


def test_renderizar_paginas_jpeg_mas_liviano_que_png_en_escaneo(tmp_path):
    """El JPEG comprimido es lo que evita los timeouts al mandar la imagen a la API."""
    ruta = tmp_path / "escaneo_simulado.pdf"
    _crear_pdf_escaneado_simulado(ruta)

    jpeg = pdf_analyzer.renderizar_paginas(str(ruta), [0])[0]
    png = pdf_analyzer.renderizar_paginas(str(ruta), [0], formato="png")[0]

    assert len(jpeg) < len(png)


def test_renderizar_paginas_avisa_por_cada_pagina(tmp_path):
    ruta = tmp_path / "tres.pdf"
    _crear_pdf(ruta, [None, None, None])
    avisadas = []

    pdf_analyzer.renderizar_paginas(str(ruta), [0, 1, 2], on_pagina=avisadas.append)

    assert avisadas == [0, 1, 2]


def test_renderizar_paginas_menor_calidad_pesa_menos(tmp_path):
    """La calidad es la palanca para controlar el peso de lo que se sube a la API."""
    ruta = tmp_path / "escaneo_simulado.pdf"
    _crear_pdf_escaneado_simulado(ruta)

    alta = pdf_analyzer.renderizar_paginas(str(ruta), [0], calidad=90)[0]
    baja = pdf_analyzer.renderizar_paginas(str(ruta), [0], calidad=40)[0]

    assert len(baja) < len(alta)
