# PDF2Word

App de escritorio portable para Windows que convierte PDFs a documentos Word
(`.docx`) preservando títulos, listas y **tablas**. Funciona tanto con PDFs
digitales como con escaneados, y detecta automáticamente de cuál se trata
página por página.

Un solo `.exe`, sin instalador y sin necesidad de tener Python en la máquina.

---

## Cómo funciona

El PDF se clasifica página por página y cada tipo sigue su propio camino:

```
                        PDF
                         │
          ┌──────────────┴──────────────┐
    página digital                 página escaneada
  (texto extraíble)              (imagen / sin texto)
          │                              │
   pdfplumber local              se renderiza a imagen
   texto + tablas                        │
   (gratis, sin red)              OCR (en paralelo)
          │                              │
          └──────────────┬───────────────┘
                         │
              Markdown (local por defecto)
                         │
                       .docx
```

**Las páginas digitales no gastan nada de API**: el texto y las tablas se
extraen localmente con pdfplumber. Solo las páginas escaneadas necesitan OCR.

---

## Proveedores de OCR

Se elige desde la pantalla de Configuración:

| Proveedor | Requiere | Velocidad | Notas |
|---|---|---|---|
| **NVIDIA NIM** (por defecto) | API key de NVIDIA | Rápido | Usa un modelo de visión; el 90B es notablemente más fiel que el 11B transcribiendo |
| **OpenRouter** | API key de OpenRouter | Rápido | Solo modelos gratuitos con entrada de imagen |
| **Local (offline)** | Nada — ni key ni internet | ~60 s/página | Necesita el proyecto `ocr-local` junto a la app |

El OCR de las páginas escaneadas corre **en paralelo** (4 a la vez por defecto),
con un limitador de llamadas por minuto para no pasarse del límite de la API.
El motor local se fuerza a 1 por vez: cada proceso carga ~4 GB de pesos y ya usa
todos los núcleos, así que paralelizarlo agota la RAM sin ganar velocidad.

---

## Estructuración del texto: sin IA por defecto

Una vez extraído el texto, hay dos formas de armar el documento:

- **Local, sin IA (por defecto).** El texto se vuelca tal cual y el formato
  (títulos, listas, tablas) se infiere con reglas simples. **Garantiza que no se
  pierda contenido.**
- **Con IA (opcional, casilla en Configuración).** El texto pasa por un LLM de
  OpenRouter que lo reformatea. Queda más prolijo, pero un modelo de lenguaje
  —por más que se le pida transcribir— omite fragmentos de forma impredecible.
  Por eso no es el default.

Si activás la opción con IA, la app detecta cuando el modelo devuelve
mucho menos texto del que se le mandó y **falla de forma visible** en vez de
entregarte un `.docx` incompleto sin avisar.

---

## Solo modelos gratuitos

La app nunca usa modelos pagos de OpenRouter. Está garantizado en dos capas:

1. La pantalla de Configuración solo lista modelos con precio 0 (consultados en
   vivo a la API de OpenRouter), y para OCR filtra además los que aceptan
   imágenes.
2. Al cargar la config, cualquier modelo que no termine en `:free` se reemplaza
   automáticamente por el default gratuito — por si alguien edita el
   `config.json` a mano.

---

## Uso

1. Abrí `PDF2Word.exe`.
2. Andá a **Configuración** y cargá la API key del proveedor de OCR que vayas a
   usar. (Si elegís el proveedor local, no hace falta ninguna key.)
   - OpenRouter: https://openrouter.ai/keys
   - NVIDIA: https://build.nvidia.com
3. **Seleccionar PDF** → **Convertir** → elegí dónde guardar el `.docx`.

La barra de progreso avanza página por página, y podés cancelar a mitad de una
conversión larga.

### Cuánto tarda

Depende del tipo de PDF. Para un documento de ~34 páginas:

- **Todas digitales:** segundos — no hay llamadas de red.
- **Todas escaneadas:** unos minutos con NVIDIA u OpenRouter (4 páginas en
  paralelo); bastante más con el motor local, que va de a una.

---

## Configuración

`config.json` se crea solo la primera vez, **junto al exe** (no en `%APPDATA%`),
para que la app sea portable de verdad.

```json
{
  "openrouter_api_key": "",
  "openrouter_model": "inclusionai/ling-3.0-flash:free",
  "openrouter_vision_model": "google/gemma-4-31b-it:free",
  "nvidia_api_key": "",
  "nvidia_vision_model": "meta/llama-3.2-90b-vision-instruct",
  "ocr_provider": "nvidia",
  "ocr_max_paralelo": 4,
  "ocr_rpm_limite": 40,
  "estructurar_con_ia": false
}
```

> ⚠️ **`config.json` guarda las API keys en texto plano.** Está en `.gitignore`,
> pero tenelo en cuenta si compartís la carpeta o el `.exe` con alguien: el
> archivo viaja al lado del ejecutable. Borralo antes de pasar la app a un
> tercero.

Los catálogos de modelos cambian seguido. Si un modelo deja de existir, la app
devuelve un error claro pidiéndote elegir otro de la lista en Configuración.

---

## Desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python app.py
```

### Tests

```powershell
.\.venv\Scripts\python -m pytest tests/ -v
```

### Build portable

```powershell
.\build.ps1
```

Genera `dist\PDF2Word.exe`: un solo archivo, sin instalador.

---

## Stack

Python 3.9+ · CustomTkinter (UI) · pdfplumber + PyMuPDF (análisis y render de
PDF) · python-docx (generación del Word) · requests · PyInstaller (empaquetado).

## Licencia

MIT — ver [LICENSE](LICENSE).
