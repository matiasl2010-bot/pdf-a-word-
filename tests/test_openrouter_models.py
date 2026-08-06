import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests
import openrouter_models


@patch("openrouter_models.requests.get")
def test_listar_modelos_gratuitos_filtra_por_precio(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"id": "google/gemini-2.0-flash-exp:free", "pricing": {"prompt": "0", "completion": "0"}},
            {"id": "anthropic/claude-3.5-sonnet", "pricing": {"prompt": "0.000003", "completion": "0.000015"}},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "pricing": {"prompt": "0", "completion": "0"}},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    modelos = openrouter_models.listar_modelos_gratuitos()

    assert modelos == ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.3-70b-instruct:free"]


@patch("openrouter_models.requests.get")
def test_listar_modelos_gratuitos_ignora_pricing_invalido(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"id": "modelo-sin-pricing"},
            {"id": "modelo-pricing-raro", "pricing": {"prompt": "no-numero", "completion": "0"}},
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    modelos = openrouter_models.listar_modelos_gratuitos()

    assert modelos == []


@patch("openrouter_models.requests.get", side_effect=requests.RequestException("timeout"))
def test_listar_modelos_gratuitos_error_de_red_lanza_error(mock_get):
    with pytest.raises(openrouter_models.OpenRouterModelsError):
        openrouter_models.listar_modelos_gratuitos()


@patch("openrouter_models.requests.get")
def test_listar_modelos_vision_gratuitos_filtra_por_modalidad_imagen(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "id": "vision/gratis:free",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"input_modalities": ["text", "image"]},
            },
            {
                "id": "solo-texto/gratis:free",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"input_modalities": ["text"]},
            },
            {
                "id": "vision/paga",
                "pricing": {"prompt": "0.000003", "completion": "0.00001"},
                "architecture": {"input_modalities": ["text", "image"]},
            },
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    modelos = openrouter_models.listar_modelos_vision_gratuitos()

    assert modelos == ["vision/gratis:free"]


@patch("openrouter_models.requests.get")
def test_listar_modelos_vision_excluye_los_que_no_sirven_para_ocr(mock_get):
    """Algunos modelos declaran entrada de imagen pero son de musica o moderacion."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "id": "google/lyria-3-pro-preview",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"input_modalities": ["text", "image"]},
            },
            {
                "id": "nvidia/nemotron-3.5-content-safety:free",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"input_modalities": ["text", "image"]},
            },
            {
                "id": "openrouter/free",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"input_modalities": ["text", "image"]},
            },
            {
                "id": "google/gemma-4-31b-it:free",
                "pricing": {"prompt": "0", "completion": "0"},
                "architecture": {"input_modalities": ["image", "text"]},
            },
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    assert openrouter_models.listar_modelos_vision_gratuitos() == ["google/gemma-4-31b-it:free"]


@patch("openrouter_models.requests.get")
def test_listar_modelos_vision_gratuitos_sin_architecture_no_rompe(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"id": "sin-architecture:free", "pricing": {"prompt": "0", "completion": "0"}}]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    assert openrouter_models.listar_modelos_vision_gratuitos() == []
