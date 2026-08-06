import requests

MODELS_URL = "https://openrouter.ai/api/v1/models"


class OpenRouterModelsError(Exception):
    pass


def _traer_modelos(timeout: int) -> list:
    try:
        response = requests.get(MODELS_URL, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        raise OpenRouterModelsError(f"Error consultando modelos de OpenRouter: {e}") from e

    return response.json().get("data", [])


def _es_gratuito(modelo: dict) -> bool:
    pricing = modelo.get("pricing", {})
    try:
        return float(pricing.get("prompt", "1")) == 0 and float(pricing.get("completion", "1")) == 0
    except (TypeError, ValueError):
        return False


# Modelos que declaran entrada de imagen pero no sirven para transcribir texto:
# generacion de musica (lyria), moderacion de contenido, routers genericos.
NO_SIRVEN_PARA_OCR = ("lyria", "content-safety", "moderation", "openrouter/free")


def _acepta_imagenes(modelo: dict) -> bool:
    modalidades = modelo.get("architecture", {}).get("input_modalities", [])
    if "image" not in modalidades:
        return False
    id_modelo = modelo.get("id", "").lower()
    return not any(p in id_modelo for p in NO_SIRVEN_PARA_OCR)


def listar_modelos_gratuitos(timeout: int = 30) -> list:
    """Ids de los modelos gratuitos (pricing prompt y completion en 0), ordenados."""
    modelos = _traer_modelos(timeout)
    return sorted(m["id"] for m in modelos if "id" in m and _es_gratuito(m))


def listar_modelos_vision_gratuitos(timeout: int = 30) -> list:
    """Ids de los modelos gratuitos que ademas aceptan imagenes (sirven para OCR)."""
    modelos = _traer_modelos(timeout)
    return sorted(m["id"] for m in modelos if "id" in m and _es_gratuito(m) and _acepta_imagenes(m))
