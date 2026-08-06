import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ocr_limpieza


def test_saca_preambulo_de_cortesia():
    crudo = "¡Claro que sí!\n\nEl texto de la imagen es el siguiente:\n\nConstructivismo\nIntroducción"

    limpio = ocr_limpieza.limpiar(crudo)

    assert limpio.startswith("Constructivismo")
    assert "Claro que sí" not in limpio
    assert "es el siguiente" not in limpio


def test_saca_notas_del_modelo_al_final():
    crudo = "Contenido real del documento.\nNota: El texto en la imagen está escrito en español."

    limpio = ocr_limpieza.limpiar(crudo)

    assert "Contenido real del documento." in limpio
    assert "está escrito en español" not in limpio


def test_saca_descripciones_de_imagen():
    crudo = (
        "La imagen muestra dos círculos con textos en español.\n"
        "Texto que si es del documento."
    )

    limpio = ocr_limpieza.limpiar(crudo)

    assert "Texto que si es del documento." in limpio
    assert "La imagen muestra" not in limpio


def test_pagina_sin_texto_queda_vacia():
    crudo = "No hay texto en la imagen. La imagen parece ser un fragmento de un documento."

    assert ocr_limpieza.limpiar(crudo).strip() == ""


def test_saca_vinetas_inventadas_en_todas_las_lineas():
    """Cuando el modelo pone '*' delante de cada linea no son listas reales."""
    crudo = "*   Constructivismo\n*   Introducción\n*   En esta lectura nos adentraremos en el tema."

    limpio = ocr_limpieza.limpiar(crudo)

    assert limpio.splitlines()[0] == "Constructivismo"
    assert not any(l.startswith("*") for l in limpio.splitlines())


def test_respeta_listas_reales():
    """Si solo algunas lineas tienen vineta, son una lista de verdad."""
    crudo = "Los tipos son:\n- primero\n- segundo\nTexto de cierre."

    limpio = ocr_limpieza.limpiar(crudo)

    assert "- primero" in limpio
    assert "- segundo" in limpio


def test_saca_cercos_de_codigo():
    crudo = "```\nContenido del documento\n```"

    limpio = ocr_limpieza.limpiar(crudo)

    assert limpio.strip() == "Contenido del documento"


def test_no_toca_texto_normal():
    crudo = "Primer parrafo del documento.\n\nSegundo parrafo con mas contenido."

    assert ocr_limpieza.limpiar(crudo) == crudo


def test_texto_vacio_no_rompe():
    assert ocr_limpieza.limpiar("") == ""
    assert ocr_limpieza.limpiar(None) == ""
