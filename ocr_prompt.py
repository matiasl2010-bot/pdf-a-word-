"""Prompt compartido por los proveedores de OCR.

Es deliberadamente estricto: los modelos de vision tienden a saludar antes de
responder, a describir la imagen y a "corregir" el texto que leen. Cualquiera de
esas tres cosas termina como contenido falso en el documento final.
"""

PROMPT_OCR = (
    "Transcribí literalmente todo el texto visible en esta imagen, respetando el "
    "orden en que aparece.\n"
    "REGLAS:\n"
    "- Copiá el texto exactamente como está. No corrijas, no reformules, no traduzcas.\n"
    "- No agregues saludos, introducciones, comentarios ni notas al final.\n"
    "- No describas la imagen ni digas en qué idioma está.\n"
    "- No agregues viñetas ni numeración que no estén en el original.\n"
    "- Si la imagen no tiene texto, respondé con una cadena vacía.\n"
    "- Respondé únicamente con el texto transcripto."
)
