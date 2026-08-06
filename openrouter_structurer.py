import logging
import time

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Un documento largo no entra en una sola respuesta: los modelos tienen un techo
# de tokens de salida muy por debajo de lo que ocupan 30+ paginas. Se manda por
# bloques y se concatenan los resultados.
MAX_CHARS_BLOQUE = 6000
MAX_TOKENS_RESPUESTA = 8000

# Si el modelo devuelve mucho menos de lo que se le mando, corto o resumio en vez
# de transcribir. Es preferible fallar visible a entregar un .docx incompleto.
RATIO_MINIMO_SALIDA = 0.35

INSTRUCCIONES = (
    "Convertí a Markdown el siguiente texto extraído de un PDF.\n"
    "REGLAS IMPORTANTES:\n"
    "- Transcribí TODO el contenido. No resumas, no omitas, no agregues comentarios.\n"
    "- Conservá todas las líneas y su orden original.\n"
    "- Usá #/## para títulos, - para listas, **negrita** donde corresponda.\n"
    "- Si hay tablas, representalas como tablas Markdown (| col | col |).\n"
    "- Respondé únicamente con el Markdown, sin explicaciones ni razonamiento previo.\n"
)

logger = logging.getLogger(__name__)


class OpenRouterError(Exception):
    pass


def _tablas_a_texto(tablas: list) -> str:
    partes = []
    for tabla in tablas:
        filas = [
            "| " + " | ".join(str(c) if c is not None else "" for c in fila) + " |"
            for fila in tabla
        ]
        partes.append("\n".join(filas))
    return "\n\n".join(partes)


def _armar_bloques(paginas: list, max_chars: int) -> list:
    """Agrupa paginas consecutivas en bloques que no superen max_chars.
    Una pagina sola siempre entra en su propio bloque, aunque exceda el limite."""
    bloques = []
    actual = []
    chars_actual = 0

    for pagina in paginas:
        largo = len(pagina.get("texto", ""))
        if actual and chars_actual + largo > max_chars:
            bloques.append(actual)
            actual = []
            chars_actual = 0
        actual.append(pagina)
        chars_actual += largo

    if actual:
        bloques.append(actual)
    return bloques


def _prompt_de_bloque(bloque: list) -> str:
    texto = "\n\n".join(p.get("texto", "") for p in bloque)
    prompt = f"{INSTRUCCIONES}\nTEXTO:\n{texto}\n"

    tablas = [t for p in bloque for t in p.get("tablas", [])]
    if tablas:
        prompt += (
            "\nTABLAS YA DETECTADAS (usalas tal cual, no las inventes de nuevo):\n"
            f"{_tablas_a_texto(tablas)}\n"
        )
    return prompt


def _pedir_bloque(prompt: str, api_key: str, modelo: str, timeout: int, intentos: int) -> str:
    payload = {
        "model": modelo,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": MAX_TOKENS_RESPUESTA,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    ultimo_error = None
    for intento in range(intentos):
        try:
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 404:
                raise OpenRouterError(
                    f"OpenRouter no reconoce el modelo '{modelo}' (404). Los catalogos cambian: "
                    "entra a Configuracion y elegi otro modelo de la lista."
                )
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
            raise OpenRouterError(f"Respuesta inesperada de OpenRouter: {data}") from e

        if not contenido or not contenido.strip():
            raise OpenRouterError("OpenRouter devolvio una respuesta vacia")
        return contenido

    raise OpenRouterError(
        f"Error llamando a OpenRouter tras {intentos} intentos: {ultimo_error}"
    ) from ultimo_error


def estructurar_markdown(
    paginas: list, api_key: str, modelo: str,
    timeout: int = 180, intentos: int = 2, on_progreso=None,
    max_chars_bloque: int = MAX_CHARS_BLOQUE,
) -> str:
    """Convierte el texto de las paginas en Markdown estructurado.

    paginas: lista de {"texto": str, "tablas": list}, en orden de documento.
    on_progreso(bloques_hechos, bloques_totales): para reportar avance en la UI.
    """
    if not api_key:
        raise OpenRouterError("Falta la API key de OpenRouter")

    bloques = _armar_bloques(paginas, max_chars_bloque)
    total = len(bloques)
    salidas = []

    for i, bloque in enumerate(bloques, start=1):
        prompt = _prompt_de_bloque(bloque)
        contenido = _pedir_bloque(prompt, api_key, modelo, timeout, intentos)

        chars_entrada = sum(len(p.get("texto", "")) for p in bloque)
        if chars_entrada > 500 and len(contenido) < chars_entrada * RATIO_MINIMO_SALIDA:
            raise OpenRouterError(
                f"El modelo '{modelo}' devolvio un contenido demasiado corto en el bloque "
                f"{i}/{total} ({len(contenido)} caracteres para {chars_entrada} enviados): "
                "esta resumiendo o truncando en vez de transcribir. Proba con otro modelo "
                "desde Configuracion."
            )

        salidas.append(contenido.strip())
        if on_progreso:
            on_progreso(i, total)

    return "\n\n".join(salidas)
