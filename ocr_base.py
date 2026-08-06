class OCRError(Exception):
    """Error base de OCR, comun a todos los proveedores.

    Vive en su propio modulo para que nvidia_ocr y openrouter_ocr puedan
    heredarlo sin importar ocr.py (que a su vez los importa a ellos)."""
