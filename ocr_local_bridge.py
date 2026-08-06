"""Puente hacia el motor de OCR offline del proyecto `apps/ocr-local`.

Vive aca (y no en ocr-local) porque este modulo se compila dentro del exe de
PDF2Word; lo que queda afuera del exe es solo el binario `focr` y los pesos.
La logica de invocacion es de `ocr-local/ocr_local.py`, que se importa si esta
disponible; si el proyecto no esta al lado, el proveedor local queda apagado.
"""

import logging
import sys
from pathlib import Path

from ocr_base import OCRError

logger = logging.getLogger(__name__)

_modulo = None
_intentado = False


def _raiz_app() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _candidatos_ocr_local() -> list:
    """Dónde puede estar el proyecto ocr-local, en dev y ya empaquetado."""
    raiz = _raiz_app()
    return [
        raiz / "ocr-local",          # paquete distribuible: junto al exe
        raiz.parent / "ocr-local",   # monorepo en desarrollo
    ]


def _cargar():
    """Importa ocr_local.py del proyecto vecino, una sola vez."""
    global _modulo, _intentado
    if _intentado:
        return _modulo
    _intentado = True

    for carpeta in _candidatos_ocr_local():
        modulo_py = carpeta / "ocr_local.py"
        if not modulo_py.is_file():
            continue
        try:
            if str(carpeta) not in sys.path:
                sys.path.insert(0, str(carpeta))
            import ocr_local  # noqa: PLC0415

            _modulo = ocr_local
            logger.info("motor de OCR local cargado desde %s", carpeta)
            return _modulo
        except ImportError as e:
            logger.warning("no se pudo importar ocr_local desde %s: %s", carpeta, e)

    logger.info("no se encontro el proyecto ocr-local; el OCR offline queda deshabilitado")
    return None


def disponible() -> bool:
    modulo = _cargar()
    if modulo is None:
        return False
    try:
        return bool(modulo.disponible())
    except Exception:
        logger.exception("fallo el chequeo del motor de OCR local")
        return False


def ocr_imagen(imagen_bytes: bytes, cfg: dict) -> str:
    modulo = _cargar()
    if modulo is None:
        raise OCRError(
            "El OCR offline no esta instalado. Falta la carpeta 'ocr-local' junto a la aplicacion."
        )
    try:
        return modulo.ocr_imagen(imagen_bytes, cfg)
    except modulo.OCRLocalError as e:
        raise OCRError(str(e)) from e
