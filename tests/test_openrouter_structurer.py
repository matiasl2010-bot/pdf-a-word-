import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests
import openrouter_structurer


def _pagina(texto, tablas=None):
    return {"texto": texto, "tablas": tablas or []}


def _respuesta_ok(contenido):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"choices": [{"message": {"content": contenido}}]}
    mock_response.raise_for_status = MagicMock()
    return mock_response


def test_estructurar_markdown_sin_api_key_lanza_error():
    with pytest.raises(openrouter_structurer.OpenRouterError):
        openrouter_structurer.estructurar_markdown([_pagina("texto")], "", "modelo-x")


@patch("openrouter_structurer.requests.post")
def test_estructurar_markdown_devuelve_contenido(mock_post):
    mock_post.return_value = _respuesta_ok("# Titulo\nTexto estructurado")

    resultado = openrouter_structurer.estructurar_markdown(
        [_pagina("texto crudo")], "or-key-123", "modelo-x"
    )

    assert resultado == "# Titulo\nTexto estructurado"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["model"] == "modelo-x"
    assert "texto crudo" in payload["messages"][0]["content"]


@patch("openrouter_structurer.requests.post")
def test_estructurar_markdown_manda_max_tokens(mock_post):
    """Sin max_tokens explicito el modelo corta la salida y se pierde contenido."""
    mock_post.return_value = _respuesta_ok("# ok")

    openrouter_structurer.estructurar_markdown([_pagina("texto")], "or-key", "modelo-x")

    payload = mock_post.call_args.kwargs["json"]
    assert payload.get("max_tokens", 0) >= 4000


@patch("openrouter_structurer.requests.post")
def test_estructurar_markdown_incluye_tablas_detectadas_en_prompt(mock_post):
    mock_post.return_value = _respuesta_ok("ok")

    tablas = [[["Componente", "Valor"], ["Resistencia", "220 ohm"]]]
    openrouter_structurer.estructurar_markdown(
        [_pagina("texto", tablas)], "or-key-123", "modelo-x"
    )

    contenido = mock_post.call_args.kwargs["json"]["messages"][0]["content"]
    assert "Resistencia" in contenido
    assert "220 ohm" in contenido


# --- Procesamiento por bloques (el bug de las 34 paginas -> 7) ---


def _respuesta_proporcional(mock_post):
    """El modelo real devuelve un markdown de largo similar al texto enviado.
    Un mock que devuelve 8 caracteres dispararia la deteccion de truncamiento."""

    def responder(*args, **kwargs):
        enviado = kwargs["json"]["messages"][0]["content"]
        return _respuesta_ok("# bloque\n" + "x" * len(enviado))

    mock_post.side_effect = responder


@patch("openrouter_structurer.requests.post")
def test_muchas_paginas_se_mandan_en_varias_llamadas(mock_post):
    """34 paginas no entran en una sola respuesta: hay que partirlas en bloques."""
    _respuesta_proporcional(mock_post)

    paginas = [_pagina("contenido de la pagina numero %d. " % n * 60) for n in range(34)]
    openrouter_structurer.estructurar_markdown(paginas, "or-key", "modelo-x")

    assert mock_post.call_count > 1, "todo se mando en una sola llamada"


@patch("openrouter_structurer.requests.post")
def test_todas_las_paginas_llegan_a_algun_bloque(mock_post):
    _respuesta_proporcional(mock_post)

    paginas = [_pagina(f"MARCADOR{n:02d} " + "relleno " * 200) for n in range(20)]
    openrouter_structurer.estructurar_markdown(paginas, "or-key", "modelo-x")

    enviado = " ".join(
        llamada.kwargs["json"]["messages"][0]["content"] for llamada in mock_post.call_args_list
    )
    for n in range(20):
        assert f"MARCADOR{n:02d}" in enviado, f"la pagina {n} no se envio a ningun bloque"


@patch("openrouter_structurer.requests.post")
def test_los_bloques_se_concatenan_en_orden(mock_post):
    contador = {"n": 0}

    def responder(*args, **kwargs):
        enviado = kwargs["json"]["messages"][0]["content"]
        i = contador["n"]
        contador["n"] += 1
        return _respuesta_ok(f"# bloque {i}\n" + "x" * len(enviado))

    mock_post.side_effect = responder

    paginas = [_pagina("relleno " * 600) for _ in range(3)]
    resultado = openrouter_structurer.estructurar_markdown(paginas, "or-key", "modelo-x")

    assert resultado.index("# bloque 0") < resultado.index("# bloque 1") < resultado.index("# bloque 2")


@patch("openrouter_structurer.requests.post")
def test_reporta_progreso_por_bloque(mock_post):
    _respuesta_proporcional(mock_post)
    eventos = []

    paginas = [_pagina("relleno " * 600) for _ in range(3)]
    openrouter_structurer.estructurar_markdown(
        paginas, "or-key", "modelo-x", on_progreso=lambda hecho, total: eventos.append((hecho, total))
    )

    assert eventos, "no reporto progreso"
    assert len(eventos) > 1, "con 3 paginas largas deberia haber varios bloques"
    assert eventos[-1][0] == eventos[-1][1], "el ultimo aviso deberia ser total/total"


@patch("openrouter_structurer.requests.post")
def test_una_sola_pagina_corta_va_en_un_solo_bloque(mock_post):
    mock_post.return_value = _respuesta_ok("# ok")

    openrouter_structurer.estructurar_markdown([_pagina("texto corto")], "or-key", "modelo-x")

    assert mock_post.call_count == 1


# --- Errores ---


@patch("openrouter_structurer.requests.post")
def test_estructurar_markdown_404_avisa_que_el_modelo_no_existe(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_post.return_value = mock_response

    with pytest.raises(openrouter_structurer.OpenRouterError) as exc:
        openrouter_structurer.estructurar_markdown([_pagina("texto")], "or-key", "modelo/retirado:free")

    assert "modelo/retirado:free" in str(exc.value)
    assert "Configuracion" in str(exc.value)
    assert mock_post.call_count == 1, "un 404 no se debe reintentar"


@patch("openrouter_structurer.requests.post", side_effect=requests.RequestException("timeout"))
def test_estructurar_markdown_error_de_red_reintenta_y_lanza(mock_post):
    with pytest.raises(openrouter_structurer.OpenRouterError):
        openrouter_structurer.estructurar_markdown([_pagina("texto")], "or-key-123", "modelo-x")

    assert mock_post.call_count == 2


@patch("openrouter_structurer.requests.post")
def test_estructurar_markdown_respuesta_vacia_lanza_error(mock_post):
    mock_post.return_value = _respuesta_ok("   ")

    with pytest.raises(openrouter_structurer.OpenRouterError):
        openrouter_structurer.estructurar_markdown([_pagina("texto")], "or-key-123", "modelo-x")


@patch("openrouter_structurer.requests.post")
def test_salida_sospechosamente_corta_lanza_error(mock_post):
    """Si el modelo devuelve una fraccion minima de lo enviado, perdio contenido."""
    mock_post.return_value = _respuesta_ok("ok")

    paginas = [_pagina("contenido real y extenso de la pagina. " * 100)]

    with pytest.raises(openrouter_structurer.OpenRouterError) as exc:
        openrouter_structurer.estructurar_markdown(paginas, "or-key", "modelo-x")

    assert "content" in str(exc.value).lower() or "corto" in str(exc.value).lower()
