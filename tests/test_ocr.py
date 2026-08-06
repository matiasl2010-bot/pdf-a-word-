import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import ocr

CFG_NVIDIA = {
    "ocr_provider": "nvidia",
    "nvidia_api_key": "nv-key",
    "nvidia_vision_model": "modelo-nv",
    "openrouter_api_key": "or-key",
    "openrouter_vision_model": "modelo-or-vision",
}

CFG_OPENROUTER = dict(CFG_NVIDIA, ocr_provider="openrouter")
CFG_LOCAL = dict(CFG_NVIDIA, ocr_provider="local")


@patch("ocr.openrouter_ocr.ocr_imagen", return_value="texto or")
@patch("ocr.nvidia_ocr.ocr_imagen", return_value="texto nv")
def test_ocr_imagen_usa_nvidia_segun_config(mock_nv, mock_or):
    resultado = ocr.ocr_imagen(b"img", CFG_NVIDIA)

    assert resultado == "texto nv"
    mock_nv.assert_called_once_with(b"img", "nv-key", "modelo-nv")
    mock_or.assert_not_called()


@patch("ocr.openrouter_ocr.ocr_imagen", return_value="texto or")
@patch("ocr.nvidia_ocr.ocr_imagen", return_value="texto nv")
def test_ocr_imagen_usa_openrouter_segun_config(mock_nv, mock_or):
    resultado = ocr.ocr_imagen(b"img", CFG_OPENROUTER)

    assert resultado == "texto or"
    mock_or.assert_called_once_with(b"img", "or-key", "modelo-or-vision")
    mock_nv.assert_not_called()


@patch("ocr.ocr_local_bridge.ocr_imagen", return_value="texto local")
@patch("ocr.nvidia_ocr.ocr_imagen", return_value="texto nv")
def test_ocr_imagen_usa_el_motor_local_segun_config(mock_nv, mock_local):
    resultado = ocr.ocr_imagen(b"img", CFG_LOCAL)

    assert resultado == "texto local"
    mock_local.assert_called_once_with(b"img", CFG_LOCAL)
    mock_nv.assert_not_called()


def test_el_motor_local_no_necesita_api_key():
    """Es la ventaja del modo offline: no hay credenciales que configurar."""
    cfg = dict(CFG_LOCAL, nvidia_api_key="", openrouter_api_key="")

    assert ocr.api_key_del_proveedor(cfg) == "no-requiere"


def test_ocr_imagen_proveedor_desconocido_lanza_error():
    cfg = dict(CFG_NVIDIA, ocr_provider="inventado")

    with pytest.raises(ocr.OCRError):
        ocr.ocr_imagen(b"img", cfg)


def test_errores_de_ambos_proveedores_son_capturables_como_ocr_error():
    """La UI atrapa un solo tipo de error sin importar el proveedor elegido."""
    import nvidia_ocr
    import openrouter_ocr

    assert issubclass(nvidia_ocr.NvidiaOCRError, ocr.OCRError)
    assert issubclass(openrouter_ocr.OpenRouterOCRError, ocr.OCRError)
