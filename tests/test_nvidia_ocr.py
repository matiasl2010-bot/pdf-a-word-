import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests
import nvidia_ocr


def test_ocr_imagen_sin_api_key_lanza_error():
    with pytest.raises(nvidia_ocr.NvidiaOCRError):
        nvidia_ocr.ocr_imagen(b"fake-png-bytes", "", "modelo-x")


@patch("nvidia_ocr.requests.post")
def test_ocr_imagen_devuelve_texto_reconocido(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Texto reconocido en la imagen"}}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    resultado = nvidia_ocr.ocr_imagen(b"fake-png-bytes", "nv-key-123", "modelo-x")

    assert resultado == "Texto reconocido en la imagen"
    assert mock_post.called


@patch("nvidia_ocr.requests.post", side_effect=requests.RequestException("timeout"))
def test_ocr_imagen_error_de_red_reintenta_y_lanza(mock_post):
    with pytest.raises(nvidia_ocr.NvidiaOCRError):
        nvidia_ocr.ocr_imagen(b"fake-png-bytes", "nv-key-123", "modelo-x")

    assert mock_post.call_count == 2


@patch("nvidia_ocr.requests.post")
def test_ocr_imagen_respuesta_inesperada_lanza_error(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"algo": "inesperado"}
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    with pytest.raises(nvidia_ocr.NvidiaOCRError):
        nvidia_ocr.ocr_imagen(b"fake-png-bytes", "nv-key-123", "modelo-x")
