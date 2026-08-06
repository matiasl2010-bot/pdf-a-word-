import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pdfplumber

import markdown_to_docx
import ocr
import openrouter_structurer
import pdf_analyzer
import texto_a_markdown
from rate_limiter import RateLimiter

MAX_PARALELO_DEFAULT = 4
RPM_LIMITE_DEFAULT = 40


class PDFInvalidoError(Exception):
    pass


class ConversionCanceladaError(Exception):
    """El usuario cancelo la conversion desde la UI."""


def _validar_pdf(pdf_path: str) -> None:
    path = Path(pdf_path)
    if not path.exists() or path.stat().st_size == 0:
        raise PDFInvalidoError(f"El archivo no existe o esta vacio: {pdf_path}")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) == 0:
                raise PDFInvalidoError("El PDF no tiene paginas")
    except PDFInvalidoError:
        raise
    except Exception as e:
        raise PDFInvalidoError(
            f"No se pudo abrir el PDF (¿corrupto o protegido con contrasena?): {e}"
        ) from e


def _ocr_en_paralelo(imagenes: dict, paginas: list, cfg: dict, avisar, chequear_cancelacion) -> dict:
    """Hace el OCR de varias paginas a la vez, respetando el limite de la API.

    Las paginas terminan desordenadas, pero el resultado vuelve indexado por
    numero de pagina, asi que el orden del documento se conserva."""
    if cfg.get("ocr_provider") == "local":
        # Cada proceso del motor local carga ~4 GB de pesos y ya usa todos los
        # nucleos: paralelizarlo agota la RAM sin ganar velocidad.
        max_paralelo = 1
        rpm = 0  # sin limite: no hay API del otro lado
    else:
        max_paralelo = max(1, int(cfg.get("ocr_max_paralelo", MAX_PARALELO_DEFAULT)))
        rpm = int(cfg.get("ocr_rpm_limite", RPM_LIMITE_DEFAULT))
    ventana = float(cfg.get("ocr_ventana_segundos", 60.0))

    limiter = RateLimiter(max_llamadas=rpm, ventana_segundos=ventana)
    total = len(paginas)
    completadas = {"n": 0}
    lock = threading.Lock()
    abortar = threading.Event()

    def trabajo(i):
        if abortar.is_set():
            raise ConversionCanceladaError("Conversion cancelada por el usuario")
        chequear_cancelacion()
        limiter.esperar_turno()
        if abortar.is_set():
            raise ConversionCanceladaError("Conversion cancelada por el usuario")
        chequear_cancelacion()

        texto = ocr.ocr_imagen(imagenes[i], cfg)

        with lock:
            completadas["n"] += 1
            avisar(f"OCR: {completadas['n']}/{total} paginas...")
        return i, texto

    resultados = {}
    with ThreadPoolExecutor(max_workers=max_paralelo) as executor:
        futuros = [executor.submit(trabajo, i) for i in paginas]
        try:
            for futuro in as_completed(futuros):
                i, texto = futuro.result()
                resultados[i] = texto
        except BaseException:
            # una pagina fallo o el usuario cancelo: cortamos las pendientes
            # para no seguir gastando llamadas a la API
            abortar.set()
            for f in futuros:
                f.cancel()
            raise

    return resultados


def convertir_pdf(
    pdf_path: str, output_path: str, cfg: dict, progreso_callback=None, cancelar_event=None
) -> None:
    def chequear_cancelacion():
        if cancelar_event is not None and cancelar_event.is_set():
            raise ConversionCanceladaError("Conversion cancelada por el usuario")

    chequear_cancelacion()

    # Antes de saber cuantas paginas hay no se puede calcular una fraccion, pero
    # la UI no puede quedarse muda mientras se analiza el PDF.
    if progreso_callback:
        progreso_callback("Analizando el PDF...", 0.0)

    _validar_pdf(pdf_path)

    tipos = pdf_analyzer.tipos_por_pagina(pdf_path)
    paginas_digitales = [i for i, t in enumerate(tipos) if t == "digital"]
    paginas_escaneadas = [i for i, t in enumerate(tipos) if t == "escaneado"]

    # Pasos: 1 por pagina digital (extraccion) + 2 por pagina escaneada
    # (renderizado a imagen + OCR) + estructurar + generar docx
    pasos_totales = len(paginas_digitales) + len(paginas_escaneadas) * 2 + 2
    paso_actual = 0
    lock_progreso = threading.Lock()

    def avisar(mensaje: str) -> None:
        """Thread-safe: durante el OCR paralelo la llaman varios hilos."""
        nonlocal paso_actual
        with lock_progreso:
            paso_actual += 1
            fraccion = paso_actual / pasos_totales
        if progreso_callback:
            progreso_callback(mensaje, fraccion)

    textos_por_pagina = {}
    tablas_por_pagina = {}

    if paginas_digitales:
        total_digitales = len(paginas_digitales)
        contador_digital = {"n": 0}

        def on_pagina_digital(_indice):
            chequear_cancelacion()
            contador_digital["n"] += 1
            avisar(f"Extrayendo texto de pagina {contador_digital['n']}/{total_digitales}...")

        extraido = pdf_analyzer.extraer_texto_y_tablas(pdf_path, paginas_digitales, on_pagina=on_pagina_digital)
        for i, datos in extraido.items():
            textos_por_pagina[i] = datos["texto"]
            tablas_por_pagina[i] = datos["tablas"]

    if paginas_escaneadas:
        chequear_cancelacion()
        total_escaneadas = len(paginas_escaneadas)
        contador_render = {"n": 0}

        def on_pagina_renderizada(_indice):
            chequear_cancelacion()
            contador_render["n"] += 1
            avisar(f"Preparando pagina {contador_render['n']}/{total_escaneadas}...")

        imagenes = pdf_analyzer.renderizar_paginas(
            pdf_path, paginas_escaneadas, on_pagina=on_pagina_renderizada
        )
        textos_por_pagina.update(
            _ocr_en_paralelo(imagenes, paginas_escaneadas, cfg, avisar, chequear_cancelacion)
        )

    chequear_cancelacion()
    paginas_para_estructurar = [
        {"texto": textos_por_pagina[i], "tablas": tablas_por_pagina.get(i, [])}
        for i in sorted(textos_por_pagina)
    ]

    # La estructuracion ocupa el anteultimo paso del total; se reparte entre sus
    # bloques para que la barra siga avanzando dentro de esta etapa.
    base_estructura = (pasos_totales - 2) / pasos_totales

    if cfg.get("estructurar_con_ia"):
        def on_bloque(hecho, total_bloques):
            chequear_cancelacion()
            if progreso_callback:
                tramo = (1 / pasos_totales) * (hecho / total_bloques)
                progreso_callback(
                    f"Estructurando con IA: bloque {hecho}/{total_bloques}...",
                    base_estructura + tramo,
                )

        if progreso_callback:
            progreso_callback("Estructurando con IA...", base_estructura)

        markdown = openrouter_structurer.estructurar_markdown(
            paginas_para_estructurar,
            cfg["openrouter_api_key"],
            cfg["openrouter_model"],
            on_progreso=on_bloque,
        )
    else:
        # Camino por defecto: conversion local, sin LLM, sin riesgo de perder texto.
        if progreso_callback:
            progreso_callback("Armando el documento...", base_estructura)
        markdown = texto_a_markdown.convertir(paginas_para_estructurar)

    paso_actual = pasos_totales - 1

    chequear_cancelacion()
    avisar("Generando documento Word...")
    markdown_to_docx.convertir(markdown, output_path)

    if progreso_callback:
        progreso_callback("Listo.", 1.0)
