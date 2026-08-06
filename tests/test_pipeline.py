import sys
import os
import threading
import time
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fitz
import pytest
import pipeline

CFG = {
    "ocr_provider": "nvidia",
    "openrouter_api_key": "or-key",
    "openrouter_model": "modelo-or",
    "openrouter_vision_model": "modelo-or-vision",
    "nvidia_api_key": "nv-key",
    "nvidia_vision_model": "modelo-nv",
    "ocr_max_paralelo": 4,
    "ocr_rpm_limite": 40,
}


def _crear_pdf(path, paginas_con_texto):
    doc = fitz.open()
    for texto in paginas_con_texto:
        page = doc.new_page()
        if texto:
            page.insert_text((72, 72), texto)
    doc.save(str(path))
    doc.close()


TEXTO_DIGITAL = "Texto de prueba con longitud suficiente para ser detectado como digital."


def test_convertir_pdf_archivo_inexistente_lanza_error(tmp_path):
    with pytest.raises(pipeline.PDFInvalidoError):
        pipeline.convertir_pdf(str(tmp_path / "no-existe.pdf"), str(tmp_path / "out.docx"), CFG)


def test_convertir_pdf_archivo_vacio_lanza_error(tmp_path):
    ruta = tmp_path / "vacio.pdf"
    ruta.write_bytes(b"")

    with pytest.raises(pipeline.PDFInvalidoError):
        pipeline.convertir_pdf(str(ruta), str(tmp_path / "out.docx"), CFG)


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.ocr.ocr_imagen")
def test_convertir_pdf_digital_no_llama_ocr(mock_ocr, mock_docx, tmp_path):
    pdf_path = tmp_path / "digital.pdf"
    _crear_pdf(pdf_path, [TEXTO_DIGITAL])
    salida = tmp_path / "out.docx"

    pipeline.convertir_pdf(str(pdf_path), str(salida), CFG)

    mock_ocr.assert_not_called()
    mock_docx.assert_called_once()
    assert "Texto de prueba" in mock_docx.call_args.args[0]


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.ocr.ocr_imagen", return_value="texto reconocido por ocr")
def test_convertir_pdf_escaneado_llama_ocr(mock_ocr, mock_docx, tmp_path):
    pdf_path = tmp_path / "escaneado.pdf"
    _crear_pdf(pdf_path, [None])
    salida = tmp_path / "out.docx"

    pipeline.convertir_pdf(str(pdf_path), str(salida), CFG)

    mock_ocr.assert_called_once()
    assert "texto reconocido por ocr" in mock_docx.call_args.args[0]


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
@patch("pipeline.ocr.ocr_imagen", return_value="texto ocr")
def test_convertir_pdf_ocr_recibe_la_config_completa(mock_ocr, mock_estructurar, mock_docx, tmp_path):
    """El pipeline delega la eleccion de proveedor al modulo ocr, pasandole la config."""
    pdf_path = tmp_path / "escaneado.pdf"
    _crear_pdf(pdf_path, [None])

    pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG)

    assert mock_ocr.call_args.args[1] == CFG


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
@patch("pipeline.ocr.ocr_imagen", return_value="texto ocr")
def test_convertir_pdf_avisa_antes_de_analizar(mock_ocr, mock_estructurar, mock_docx, tmp_path):
    """El analisis inicial no puede dejar la UI muda: tiene que avisar primero."""
    pdf_path = tmp_path / "escaneado.pdf"
    _crear_pdf(pdf_path, [None])
    eventos = []

    with patch("pipeline.pdf_analyzer.tipos_por_pagina", wraps=pipeline.pdf_analyzer.tipos_por_pagina) as mock_tipos:
        avisos_antes_del_analisis = []

        def registrar(mensaje, fraccion):
            eventos.append((mensaje, fraccion))
            if not mock_tipos.called:
                avisos_antes_del_analisis.append(mensaje)

        pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG, progreso_callback=registrar)

    assert avisos_antes_del_analisis, "no hubo ningun aviso antes de analizar el PDF"
    assert "Analizando" in avisos_antes_del_analisis[0]
    assert eventos[0][1] == 0.0


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
@patch("pipeline.ocr.ocr_imagen", return_value="texto ocr")
def test_convertir_pdf_reporta_progreso(mock_ocr, mock_estructurar, mock_docx, tmp_path):
    pdf_path = tmp_path / "mixto.pdf"
    _crear_pdf(pdf_path, [TEXTO_DIGITAL, None])
    salida = tmp_path / "out.docx"
    eventos = []

    pipeline.convertir_pdf(
        str(pdf_path), str(salida), CFG, progreso_callback=lambda mensaje, fraccion: eventos.append((mensaje, fraccion))
    )

    assert len(eventos) >= 3
    fracciones = [f for _, f in eventos]
    assert fracciones == sorted(fracciones)
    assert fracciones[-1] == 1.0
    assert all(0.0 <= f <= 1.0 for f in fracciones)


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
def test_convertir_pdf_reporta_progreso_por_cada_pagina_digital(mock_estructurar, mock_docx, tmp_path):
    pdf_path = tmp_path / "tres_paginas.pdf"
    _crear_pdf(pdf_path, [TEXTO_DIGITAL, TEXTO_DIGITAL, TEXTO_DIGITAL])
    salida = tmp_path / "out.docx"
    eventos = []

    pipeline.convertir_pdf(
        str(pdf_path), str(salida), CFG, progreso_callback=lambda mensaje, fraccion: eventos.append((mensaje, fraccion))
    )

    mensajes_extraccion = [m for m, _ in eventos if m.startswith("Extrayendo texto de pagina")]
    assert mensajes_extraccion == [
        "Extrayendo texto de pagina 1/3...",
        "Extrayendo texto de pagina 2/3...",
        "Extrayendo texto de pagina 3/3...",
    ]


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
@patch("pipeline.ocr.ocr_imagen", return_value="texto ocr")
def test_convertir_pdf_reporta_progreso_por_cada_pagina_escaneada(mock_ocr, mock_estructurar, mock_docx, tmp_path):
    pdf_path = tmp_path / "dos_escaneadas.pdf"
    _crear_pdf(pdf_path, [None, None])
    salida = tmp_path / "out.docx"
    eventos = []

    pipeline.convertir_pdf(
        str(pdf_path), str(salida), CFG, progreso_callback=lambda mensaje, fraccion: eventos.append((mensaje, fraccion))
    )

    # con OCR en paralelo el orden de finalizacion no es determinista, pero la
    # cuenta de paginas completadas si lo es
    mensajes_ocr = [m for m, _ in eventos if m.startswith("OCR:")]
    assert mensajes_ocr == ["OCR: 1/2 paginas...", "OCR: 2/2 paginas..."]
    assert mock_ocr.call_count == 2


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
def test_convertir_pdf_hace_ocr_en_paralelo(mock_estructurar, mock_docx, tmp_path):
    """Con 4 paginas y 4 workers, las 4 llamadas se solapan en el tiempo."""
    pdf_path = tmp_path / "cuatro_escaneadas.pdf"
    _crear_pdf(pdf_path, [None, None, None, None])

    en_vuelo = []
    max_simultaneas = [0]
    lock = threading.Lock()

    PAUSA = 0.15
    marcas = []  # (inicio, fin) de cada llamada de OCR

    def ocr_lento(imagen_bytes, cfg):
        arranco = time.monotonic()
        with lock:
            en_vuelo.append(1)
            max_simultaneas[0] = max(max_simultaneas[0], len(en_vuelo))
        time.sleep(PAUSA)
        with lock:
            en_vuelo.pop()
            marcas.append((arranco, time.monotonic()))
        return "texto ocr"

    with patch("pipeline.ocr.ocr_imagen", side_effect=ocr_lento):
        pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG)

    assert max_simultaneas[0] >= 2, "las llamadas de OCR no se solaparon"

    # Se mide solo la ventana de OCR, no el total de convertir_pdf: abrir el PDF,
    # clasificar paginas y renderizarlas suma un costo fijo que no tiene nada que
    # ver con el paralelismo y hacia flakear la asercion.
    ventana_ocr = max(fin for _, fin in marcas) - min(ini for ini, _ in marcas)
    secuencial = PAUSA * len(marcas)
    assert ventana_ocr < secuencial * 0.65, (
        f"el OCR tardo {ventana_ocr:.2f}s; secuencial serian {secuencial:.2f}s - no parece paralelo"
    )


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
def test_convertir_pdf_respeta_el_maximo_de_paralelismo(mock_estructurar, mock_docx, tmp_path):
    pdf_path = tmp_path / "seis_escaneadas.pdf"
    _crear_pdf(pdf_path, [None] * 6)
    cfg = dict(CFG, ocr_max_paralelo=2)

    en_vuelo = []
    max_simultaneas = [0]
    lock = threading.Lock()

    def ocr_lento(imagen_bytes, _cfg):
        with lock:
            en_vuelo.append(1)
            max_simultaneas[0] = max(max_simultaneas[0], len(en_vuelo))
        time.sleep(0.1)
        with lock:
            en_vuelo.pop()
        return "texto ocr"

    with patch("pipeline.ocr.ocr_imagen", side_effect=ocr_lento):
        pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), cfg)

    assert max_simultaneas[0] <= 2


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
def test_convertir_pdf_respeta_el_rate_limit(mock_estructurar, mock_docx, tmp_path):
    """Con limite de 2 llamadas por ventana, la 3ra pagina espera."""
    pdf_path = tmp_path / "tres_escaneadas.pdf"
    _crear_pdf(pdf_path, [None, None, None])
    # 2 llamadas por minuto seria demasiado lento para un test: uso la ventana
    # corta que expone el pipeline para poder verificarlo rapido
    cfg = dict(CFG, ocr_max_paralelo=4, ocr_rpm_limite=2, ocr_ventana_segundos=0.5)

    with patch("pipeline.ocr.ocr_imagen", return_value="texto ocr"):
        inicio = time.monotonic()
        pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), cfg)
        transcurrido = time.monotonic() - inicio

    assert transcurrido >= 0.45


@patch("pipeline.markdown_to_docx.convertir")
def test_convertir_pdf_ocr_mantiene_el_orden_de_paginas(mock_docx, tmp_path):
    """Aunque terminen desordenadas, el texto se concatena en orden de pagina."""
    pdf_path = tmp_path / "tres_escaneadas.pdf"
    _crear_pdf(pdf_path, [None, None, None])
    # la primera pagina tarda mas, asi termina ultima
    contador = {"n": 0}
    lock = threading.Lock()

    def ocr_desordenado(imagen_bytes, _cfg):
        with lock:
            contador["n"] += 1
            n = contador["n"]
        time.sleep(0.15 if n == 1 else 0.01)
        return f"pagina-{n}"

    with patch("pipeline.ocr.ocr_imagen", side_effect=ocr_desordenado):
        pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG)

    markdown = mock_docx.call_args.args[0]
    assert markdown.index("pagina-1") < markdown.index("pagina-2") < markdown.index("pagina-3")


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
def test_convertir_pdf_error_en_una_pagina_propaga(mock_estructurar, mock_docx, tmp_path):
    from ocr_base import OCRError

    pdf_path = tmp_path / "tres_escaneadas.pdf"
    _crear_pdf(pdf_path, [None, None, None])
    contador = {"n": 0}
    lock = threading.Lock()

    def ocr_que_falla(imagen_bytes, _cfg):
        with lock:
            contador["n"] += 1
            n = contador["n"]
        if n == 2:
            raise OCRError("fallo la pagina 2")
        return "texto ocr"

    with patch("pipeline.ocr.ocr_imagen", side_effect=ocr_que_falla):
        with pytest.raises(OCRError):
            pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG)

    mock_docx.assert_not_called()


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
def test_convertir_pdf_solo_digital_llega_a_fraccion_completa(mock_estructurar, mock_docx, tmp_path):
    pdf_path = tmp_path / "digital.pdf"
    _crear_pdf(pdf_path, [TEXTO_DIGITAL])
    salida = tmp_path / "out.docx"
    eventos = []

    pipeline.convertir_pdf(
        str(pdf_path), str(salida), CFG, progreso_callback=lambda mensaje, fraccion: eventos.append((mensaje, fraccion))
    )

    assert eventos[-1] == ("Listo.", 1.0)


@patch("pipeline.markdown_to_docx.convertir")
def test_el_motor_local_no_se_paraleliza(mock_docx, tmp_path):
    """Cada proceso local carga ~4 GB: en paralelo se acaba la RAM."""
    pdf_path = tmp_path / "cuatro.pdf"
    _crear_pdf(pdf_path, [None] * 4)
    cfg = dict(CFG, ocr_provider="local", ocr_max_paralelo=4)

    en_vuelo = []
    max_simultaneas = [0]
    lock = threading.Lock()

    def ocr_lento(imagen_bytes, _cfg):
        with lock:
            en_vuelo.append(1)
            max_simultaneas[0] = max(max_simultaneas[0], len(en_vuelo))
        time.sleep(0.05)
        with lock:
            en_vuelo.pop()
        return "texto local"

    with patch("pipeline.ocr.ocr_imagen", side_effect=ocr_lento):
        pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), cfg)

    assert max_simultaneas[0] == 1, "el motor local no debe correr en paralelo"


# --- Estructuracion: local (default) vs IA ---


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown")
@patch("pipeline.ocr.ocr_imagen", return_value="TEXTO RECONOCIDO POR OCR")
def test_por_defecto_no_usa_el_llm_para_estructurar(mock_ocr, mock_llm, mock_docx, tmp_path):
    """El default no puede perder contenido: no pasa por el LLM."""
    pdf_path = tmp_path / "escaneado.pdf"
    _crear_pdf(pdf_path, [None])

    pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG)

    mock_llm.assert_not_called()
    markdown_generado = mock_docx.call_args.args[0]
    assert "TEXTO RECONOCIDO POR OCR" in markdown_generado


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Con IA")
@patch("pipeline.ocr.ocr_imagen", return_value="texto ocr")
def test_con_la_opcion_activada_usa_el_llm(mock_ocr, mock_llm, mock_docx, tmp_path):
    pdf_path = tmp_path / "escaneado.pdf"
    _crear_pdf(pdf_path, [None])
    cfg = dict(CFG, estructurar_con_ia=True)

    pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), cfg)

    mock_llm.assert_called_once()
    mock_docx.assert_called_once_with("# Con IA", str(tmp_path / "out.docx"))


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.ocr.ocr_imagen")
def test_conversion_local_conserva_todas_las_paginas(mock_ocr, mock_docx, tmp_path):
    pdf_path = tmp_path / "muchas.pdf"
    _crear_pdf(pdf_path, [None] * 34)
    mock_ocr.side_effect = lambda img, cfg: f"MARCADOR{mock_ocr.call_count:02d}"

    pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG)

    markdown = mock_docx.call_args.args[0]
    for n in range(1, 35):
        assert f"MARCADOR{n:02d}" in markdown, f"se perdio la pagina {n}"


# --- Cancelacion ---


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
@patch("pipeline.ocr.ocr_imagen", return_value="texto ocr")
def test_convertir_pdf_cancelado_antes_de_empezar_no_genera_docx(mock_ocr, mock_estructurar, mock_docx, tmp_path):
    pdf_path = tmp_path / "digital.pdf"
    _crear_pdf(pdf_path, [TEXTO_DIGITAL])
    cancelar = threading.Event()
    cancelar.set()

    with pytest.raises(pipeline.ConversionCanceladaError):
        pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG, cancelar_event=cancelar)

    mock_docx.assert_not_called()
    mock_estructurar.assert_not_called()


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
def test_convertir_pdf_cancela_durante_el_ocr(mock_estructurar, mock_docx, tmp_path):
    """Cancelar durante el OCR corta sin procesar todas las paginas restantes."""
    pdf_path = tmp_path / "muchas_escaneadas.pdf"
    _crear_pdf(pdf_path, [None] * 12)
    cancelar = threading.Event()
    cfg = dict(CFG, ocr_max_paralelo=2)
    llamadas = {"n": 0}
    lock = threading.Lock()

    def ocr_que_cancela(imagen_bytes, _cfg):
        with lock:
            llamadas["n"] += 1
            n = llamadas["n"]
        time.sleep(0.02)
        if n >= 2:
            cancelar.set()  # el usuario aprieta Cancelar al arrancar
        return "texto ocr"

    with patch("pipeline.ocr.ocr_imagen", side_effect=ocr_que_cancela):
        with pytest.raises(pipeline.ConversionCanceladaError):
            pipeline.convertir_pdf(
                str(pdf_path), str(tmp_path / "out.docx"), cfg, cancelar_event=cancelar
            )

    assert llamadas["n"] < 12, "deberia haber cortado antes de procesar todas las paginas"
    mock_estructurar.assert_not_called()
    mock_docx.assert_not_called()


@patch("pipeline.markdown_to_docx.convertir")
@patch("pipeline.openrouter_structurer.estructurar_markdown", return_value="# Titulo")
def test_convertir_pdf_sin_cancelacion_funciona_igual(mock_estructurar, mock_docx, tmp_path):
    pdf_path = tmp_path / "digital.pdf"
    _crear_pdf(pdf_path, [TEXTO_DIGITAL])
    cancelar = threading.Event()  # nunca se activa

    pipeline.convertir_pdf(str(pdf_path), str(tmp_path / "out.docx"), CFG, cancelar_event=cancelar)

    mock_docx.assert_called_once()
