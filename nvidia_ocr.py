import base64
import time

import requests

import ocr_limpieza
from ocr_base import OCRError
from ocr_prompt import PROMPT_OCR

NVIDIA_OCR_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


class NvidiaOCRError(OCRError):
    pass


def ocr_imagen(
    imagen_bytes: bytes, api_key: str, modelo: str,
    timeout: int = 180, intentos: int = 2, mime: str = "image/jpeg",
) -> str:
    if not api_key:
        raise NvidiaOCRError("Falta la API key de NVIDIA")

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
        "max_tokens": 4096,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    ultimo_error = None
    for intento in range(intentos):
        try:
            response = requests.post(NVIDIA_OCR_URL, headers=headers, json=payload, timeout=timeout)
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
            raise NvidiaOCRError(f"Respuesta inesperada de NVIDIA NIM: {data}") from e
        return ocr_limpieza.limpiar(contenido)

    raise NvidiaOCRError(f"Error llamando a NVIDIA NIM tras {intentos} intentos: {ultimo_error}") from ultimo_error
