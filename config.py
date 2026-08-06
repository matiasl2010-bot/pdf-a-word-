import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "openrouter_api_key": "",
    # Modelos verificados contra la API de OpenRouter (2026-08-03). Los catalogos
    # cambian: si alguno desaparece, la app devuelve 404 y hay que elegir otro
    # desde la pantalla de Configuracion, que lista los vigentes.
    "openrouter_model": "inclusionai/ling-3.0-flash:free",
    "openrouter_vision_model": "google/gemma-4-31b-it:free",
    "nvidia_api_key": "",
    # El 90B es notablemente mas fiel que el 11B transcribiendo: el chico llega a
    # cambiar palabras clave (leer "constructivismo" donde dice "conductismo").
    # Tarda mas por pagina, pero el paralelismo lo compensa.
    "nvidia_vision_model": "meta/llama-3.2-90b-vision-instruct",
    # Quien hace el OCR de las paginas escaneadas: "nvidia", "openrouter" o
    # "local" (offline, sin credenciales, pero ~60 s por pagina en CPU).
    "ocr_provider": "nvidia",
    # Cuantas paginas se procesan a la vez y cuantas llamadas por minuto se
    # permiten (NVIDIA NIM ronda las 40 rpm; los modelos free de OpenRouter
    # suelen ser mas restrictivos).
    "ocr_max_paralelo": 4,
    "ocr_rpm_limite": 40,
    # Si es True, el texto pasa por un LLM que lo reformatea (queda mas prolijo
    # pero puede omitir fragmentos). Por defecto False: el texto se vuelca tal
    # cual, sin riesgo de perder contenido.
    "estructurar_con_ia": False,
}

LIMITES_ENTEROS = {
    "ocr_max_paralelo": (1, 16),
    "ocr_rpm_limite": (1, 1000),
}


def get_config_path() -> Path:
    """Devuelve la ruta de config.json junto al exe (o al script en dev)."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return base / "config.json"


def load_config() -> dict:
    ruta = get_config_path()
    if not ruta.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("config.json corrupto o ilegible (%s), regenerando default", e)
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    cfg = dict(DEFAULT_CONFIG)
    cfg.update(datos)

    for clave in ("openrouter_model", "openrouter_vision_model"):
        if not cfg.get(clave, "").endswith(":free"):
            logger.warning(
                "%s '%s' no es un modelo gratuito, se reemplaza por el default (%s)",
                clave, cfg.get(clave), DEFAULT_CONFIG[clave],
            )
            cfg[clave] = DEFAULT_CONFIG[clave]

    if cfg.get("ocr_provider") not in ("nvidia", "openrouter", "local"):
        logger.warning(
            "ocr_provider '%s' invalido, se reemplaza por el default (%s)",
            cfg.get("ocr_provider"), DEFAULT_CONFIG["ocr_provider"],
        )
        cfg["ocr_provider"] = DEFAULT_CONFIG["ocr_provider"]

    for clave, (minimo, maximo) in LIMITES_ENTEROS.items():
        try:
            valor = int(cfg.get(clave))
        except (TypeError, ValueError):
            valor = None
        if valor is None or not (minimo <= valor <= maximo):
            logger.warning(
                "%s '%s' fuera de rango [%s-%s], se reemplaza por el default (%s)",
                clave, cfg.get(clave), minimo, maximo, DEFAULT_CONFIG[clave],
            )
            valor = DEFAULT_CONFIG[clave]
        cfg[clave] = valor

    return cfg


def save_config(cfg: dict) -> None:
    ruta = get_config_path()
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
