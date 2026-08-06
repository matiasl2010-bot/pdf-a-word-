"""Punto unico de entrada al OCR: despacha al proveedor elegido en la config."""

import nvidia_ocr
import ocr_local_bridge
import openrouter_ocr
from ocr_base import OCRError

PROVEEDORES = ("nvidia", "openrouter", "local")

# El motor local no usa credenciales; este centinela evita que la UI lo trate
# como "falta configurar la API key".
SIN_CREDENCIAL = "no-requiere"


def ocr_imagen(imagen_bytes: bytes, cfg: dict) -> str:
    proveedor = cfg.get("ocr_provider", "nvidia")

    if proveedor == "nvidia":
        return nvidia_ocr.ocr_imagen(imagen_bytes, cfg["nvidia_api_key"], cfg["nvidia_vision_model"])
    if proveedor == "openrouter":
        return openrouter_ocr.ocr_imagen(
            imagen_bytes, cfg["openrouter_api_key"], cfg["openrouter_vision_model"]
        )
    if proveedor == "local":
        return ocr_local_bridge.ocr_imagen(imagen_bytes, cfg)

    raise OCRError(f"Proveedor de OCR desconocido: {proveedor}")


def api_key_del_proveedor(cfg: dict) -> str:
    """Devuelve la API key que hace falta segun el proveedor de OCR elegido."""
    proveedor = cfg.get("ocr_provider")
    if proveedor == "local":
        return SIN_CREDENCIAL
    if proveedor == "openrouter":
        return cfg.get("openrouter_api_key", "")
    return cfg.get("nvidia_api_key", "")


def local_disponible() -> bool:
    """True si el motor offline esta instalado junto a la aplicacion."""
    return ocr_local_bridge.disponible()
