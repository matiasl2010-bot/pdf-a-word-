import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config


def test_load_config_sin_archivo_devuelve_default(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    cfg = config.load_config()

    assert cfg == config.DEFAULT_CONFIG
    assert ruta.exists()


def test_save_y_load_config_persiste_valores(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["openrouter_api_key"] = "sk-or-test123"
    config.save_config(nuevo)

    cargado = config.load_config()

    assert cargado["openrouter_api_key"] == "sk-or-test123"


def test_load_config_json_corrupto_devuelve_default(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    ruta.write_text("{esto no es json valido", encoding="utf-8")
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    cfg = config.load_config()

    assert cfg == config.DEFAULT_CONFIG


def test_load_config_modelo_no_gratuito_se_reemplaza_por_default(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["openrouter_model"] = "anthropic/claude-3.5-sonnet"
    config.save_config(nuevo)

    cfg = config.load_config()

    assert cfg["openrouter_model"] == config.DEFAULT_CONFIG["openrouter_model"]


def test_load_config_modelo_gratuito_se_respeta(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["openrouter_model"] = "meta-llama/llama-3.3-70b-instruct:free"
    config.save_config(nuevo)

    cfg = config.load_config()

    assert cfg["openrouter_model"] == "meta-llama/llama-3.3-70b-instruct:free"


def test_load_config_modelo_vision_no_gratuito_se_reemplaza(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["openrouter_vision_model"] = "openai/gpt-4o"
    config.save_config(nuevo)

    cfg = config.load_config()

    assert cfg["openrouter_vision_model"] == config.DEFAULT_CONFIG["openrouter_vision_model"]


def test_load_config_proveedor_ocr_invalido_se_reemplaza(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["ocr_provider"] = "proveedor-inventado"
    config.save_config(nuevo)

    cfg = config.load_config()

    assert cfg["ocr_provider"] == "nvidia"


def test_load_config_proveedor_ocr_openrouter_se_respeta(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["ocr_provider"] = "openrouter"
    config.save_config(nuevo)

    cfg = config.load_config()

    assert cfg["ocr_provider"] == "openrouter"


def test_load_config_paralelismo_fuera_de_rango_se_reemplaza(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["ocr_max_paralelo"] = 500  # excede el maximo permitido
    nuevo["ocr_rpm_limite"] = 0
    config.save_config(nuevo)

    cfg = config.load_config()

    assert cfg["ocr_max_paralelo"] == config.DEFAULT_CONFIG["ocr_max_paralelo"]
    assert cfg["ocr_rpm_limite"] == config.DEFAULT_CONFIG["ocr_rpm_limite"]


def test_load_config_paralelismo_no_numerico_se_reemplaza(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["ocr_max_paralelo"] = "muchos"
    config.save_config(nuevo)

    cfg = config.load_config()

    assert cfg["ocr_max_paralelo"] == config.DEFAULT_CONFIG["ocr_max_paralelo"]


def test_load_config_paralelismo_valido_se_respeta(tmp_path, monkeypatch):
    ruta = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: ruta)

    nuevo = dict(config.DEFAULT_CONFIG)
    nuevo["ocr_max_paralelo"] = 8
    nuevo["ocr_rpm_limite"] = 20
    config.save_config(nuevo)

    cfg = config.load_config()

    assert cfg["ocr_max_paralelo"] == 8
    assert cfg["ocr_rpm_limite"] == 20
