import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests
import openrouter_ocr


def test_ocr_imagen_sin_api_key_lanza_error():
    with pytest.raises(openrouter_ocr.OpenRouterOCRError):
        openrouter_ocr.ocr_imagen(b"fake-jpeg-bytes", "", "modelo-vision")


@patch("openrouter_ocr.requests.post")
def test_ocr_imagen_devuelve_texto_reconocido(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Texto reconocido por OpenRouter"}}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    resultado = openrouter_ocr.ocr_imagen(b"fake-jpeg-bytes", "or-key-123", "modelo-vision")

    assert resultado == "Texto reconocido por OpenRouter"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["model"] == "modelo-vision"
    contenido = payload["messages"][0]["content"]
    assert any(p.get("type") == "image_url" for p in contenido)


@patch("openrouter_ocr.requests.post", side_effect=requests.RequestException("timeout"))
def test_ocr_imagen_error_de_red_reintenta_y_lanza(mock_post):
    with pytest.raises(openrouter_ocr.OpenRouterOCRError):
        openrouter_ocr.ocr_imagen(b"fake-jpeg-bytes", "or-key-123", "modelo-vision")

    assert mock_post.call_count == 2


@patch("openrouter_ocr.requests.post")
def test_ocr_imagen_respuesta_inesperada_lanza_error(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"algo": "inesperado"}
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    with pytest.raises(openrouter_ocr.OpenRouterOCRError):
        openrouter_ocr.ocr_imagen(b"fake-jpeg-bytes", "or-key-123", "modelo-vision")
