import base64
import time

import requests

import ocr_limpieza
from ocr_base import OCRError
from ocr_prompt import PROMPT_OCR

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterOCRError(OCRError):
    pass


def ocr_imagen(
    imagen_bytes: bytes, api_key: str, modelo: str,
    timeout: int = 180, intentos: int = 2, mime: str = "image/jpeg",
) -> str:
    """OCR de una pagina usando un modelo de vision de OpenRouter.
    Mismo contrato que nvidia_ocr.ocr_imagen, para que sean intercambiables."""
    if not api_key:
        raise OpenRouterOCRError("Falta la API key de OpenRouter")

    imagen_b64 = base64.b64encode(imagen_bytes).decode("utf-8")
    payload = {
        "model": modelo,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT_OCR},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{imagen_b64}"}},
                ],
            }
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    ultimo_error = None
    for intento in range(intentos):
        try:
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 404:
                raise OpenRouterOCRError(
                    f"OpenRouter no reconoce el modelo de vision '{modelo}' (404). Los catalogos "
                    "cambian: entra a Configuracion y elegi otro modelo de la lista."
                )
            response.raise_for_status()
        except requests.RequestException as e:
            ultimo_error = e
            if intento < intentos - 1:
                time.sleep(1)
            continue

        data = response.json()
        try:
            contenido = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise OpenRouterOCRError(f"Respuesta inesperada de OpenRouter: {data}") from e
        return ocr_limpieza.limpiar(contenido)

    raise OpenRouterOCRError(
        f"Error llamando a OpenRouter (OCR) tras {intentos} intentos: {ultimo_error}"
    ) from ultimo_error
