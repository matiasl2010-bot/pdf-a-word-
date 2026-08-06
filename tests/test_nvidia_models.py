import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests
import nvidia_models


def test_listar_modelos_vision_sin_api_key_lanza_error():
    with pytest.raises(nvidia_models.NvidiaModelsError):
        nvidia_models.listar_modelos_vision("")


@patch("nvidia_models.requests.get")
def test_listar_modelos_vision_filtra_por_nombre(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"id": "meta/llama-3.2-90b-vision-instruct"},
            {"id": "meta/llama-3.1-8b-instruct"},
            {"id": "microsoft/phi-3.5-vision-instruct"},
            {"id": "nvidia/neva-22b"},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    modelos = nvidia_models.listar_modelos_vision("nv-key")

    assert "meta/llama-3.2-90b-vision-instruct" in modelos
    assert "microsoft/phi-3.5-vision-instruct" in modelos
    assert "meta/llama-3.1-8b-instruct" not in modelos


@patch("nvidia_models.requests.get")
def test_listar_modelos_todos_no_filtra(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": "a/uno"}, {"id": "b/dos-vision"}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    assert nvidia_models.listar_modelos("nv-key") == ["a/uno", "b/dos-vision"]


@patch("nvidia_models.requests.get", side_effect=requests.RequestException("timeout"))
def test_listar_modelos_error_de_red_lanza_error(mock_get):
    with pytest.raises(nvidia_models.NvidiaModelsError):
        nvidia_models.listar_modelos("nv-key")
