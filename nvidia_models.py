"""Listado de modelos disponibles en NVIDIA NIM.

Nota: a diferencia de OpenRouter, la API de NVIDIA no expone precios, asi que no
se puede filtrar por "gratuito" — en build.nvidia.com los modelos se usan con los
creditos de trial de la cuenta. Lo que si se puede es acotar la lista a los
modelos con capacidad de vision, que son los unicos que sirven para OCR."""

import requests

MODELS_URL = "https://integrate.api.nvidia.com/v1/models"

# NVIDIA no declara modalidades en su listado; los modelos de vision se
# reconocen por el nombre.
PALABRAS_VISION = ("vision", "vlm", "neva", "vila", "florence", "ocr", "paddle")


class NvidiaModelsError(Exception):
    pass


def listar_modelos(api_key: str, timeout: int = 30) -> list:
    if not api_key:
        raise NvidiaModelsError("Falta la API key de NVIDIA")

    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = requests.get(MODELS_URL, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        raise NvidiaModelsError(f"Error consultando modelos de NVIDIA: {e}") from e

    return [m["id"] for m in response.json().get("data", []) if "id" in m]


def listar_modelos_vision(api_key: str, timeout: int = 30) -> list:
    modelos = listar_modelos(api_key, timeout)
    return sorted(m for m in modelos if any(p in m.lower() for p in PALABRAS_VISION))
