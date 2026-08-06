import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import texto_a_markdown


def _pagina(texto, tablas=None):
    return {"texto": texto, "tablas": tablas or []}


def test_conserva_todo_el_texto():
    """Es la garantia central: sin LLM de por medio, no se pierde ni una linea."""
    paginas = [_pagina(f"MARCADOR{n:02d}\nContenido de la pagina {n}.") for n in range(50)]

    salida = texto_a_markdown.convertir(paginas)

    for n in range(50):
        assert f"MARCADOR{n:02d}" in salida
        assert f"Contenido de la pagina {n}." in salida


def test_respeta_el_orden_de_las_paginas():
    paginas = [_pagina("primera"), _pagina("segunda"), _pagina("tercera")]

    salida = texto_a_markdown.convertir(paginas)

    assert salida.index("primera") < salida.index("segunda") < salida.index("tercera")


def test_detecta_titulos_en_mayusculas():
    paginas = [_pagina("INTRODUCCION GENERAL\nEste es el cuerpo del texto que sigue.")]

    salida = texto_a_markdown.convertir(paginas)

    assert "# INTRODUCCION GENERAL" in salida


def test_detecta_titulos_numerados():
    paginas = [_pagina("1. Conceptos basicos\nTexto del apartado que desarrolla el tema.")]

    salida = texto_a_markdown.convertir(paginas)

    assert "## 1. Conceptos basicos" in salida


def test_detecta_listas_con_distintos_simbolos():
    paginas = [_pagina("- primer item\n* segundo item\n• tercer item")]

    salida = texto_a_markdown.convertir(paginas)

    assert "- primer item" in salida
    assert "- segundo item" in salida
    assert "- tercer item" in salida


def test_convierte_tablas_detectadas():
    tabla = [["Componente", "Valor"], ["Resistencia", "220 ohm"]]
    paginas = [_pagina("Texto previo", [tabla])]

    salida = texto_a_markdown.convertir(paginas)

    assert "| Componente | Valor |" in salida
    assert "| Resistencia | 220 ohm |" in salida
    assert "| --- | --- |" in salida


def test_tabla_con_celdas_vacias_no_rompe():
    tabla = [["A", None], [None, "B"]]
    paginas = [_pagina("", [tabla])]

    salida = texto_a_markdown.convertir(paginas)

    assert "| A |  |" in salida


def test_paginas_vacias_no_generan_ruido():
    paginas = [_pagina(""), _pagina("contenido real"), _pagina("   ")]

    salida = texto_a_markdown.convertir(paginas)

    assert "contenido real" in salida
    assert "\n\n\n\n" not in salida


def test_texto_normal_queda_como_parrafo():
    paginas = [_pagina("Esta es una oracion comun y corriente que deberia quedar como parrafo.")]

    salida = texto_a_markdown.convertir(paginas)

    assert salida.strip() == "Esta es una oracion comun y corriente que deberia quedar como parrafo."


def test_lista_vacia_de_paginas():
    assert texto_a_markdown.convertir([]) == ""
