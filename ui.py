import logging
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk

import config
import nvidia_models
import ocr
import openrouter_models
import openrouter_structurer
import pipeline
from ocr_base import OCRError

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

ETIQUETAS_PROVEEDOR = {
    "local": "Offline, en esta PC (sin internet)",
    "nvidia": "NVIDIA NIM",
    "openrouter": "OpenRouter (modelos gratuitos)",
}
PROVEEDOR_POR_ETIQUETA = {v: k for k, v in ETIQUETAS_PROVEEDOR.items()}


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PDF a Word")
        self.geometry("520x460")

        self.cfg = config.load_config()
        self.pdf_path = None
        self.cancelar_event = None

        self._construir_pantalla_principal()

    # --- Pantalla principal ---

    def _construir_pantalla_principal(self):
        for widget in self.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self, text="PDF -> Word Converter", font=("Segoe UI", 18, "bold")).pack(pady=(20, 10))

        self.label_archivo = ctk.CTkLabel(self, text="Ningun archivo seleccionado")
        self.label_archivo.pack(pady=5)

        ctk.CTkButton(self, text="Seleccionar PDF", command=self._seleccionar_pdf).pack(pady=5)
        ctk.CTkButton(self, text="Configuracion", command=self._construir_pantalla_config).pack(pady=5)

        self.label_ocr_activo = ctk.CTkLabel(
            self,
            text=self._resumen_configuracion(),
            text_color="gray",
        )
        self.label_ocr_activo.pack(pady=(8, 0))

        fila_botones = ctk.CTkFrame(self, fg_color="transparent")
        fila_botones.pack(pady=15)

        self.boton_convertir = ctk.CTkButton(
            fila_botones, text="Convertir", command=self._iniciar_conversion, state="disabled"
        )
        self.boton_convertir.pack(side="left", padx=5)

        self.boton_cancelar = ctk.CTkButton(
            fila_botones, text="Cancelar", command=self._cancelar_conversion,
            state="disabled", fg_color="#8B2E2E", hover_color="#A63A3A",
        )
        self.boton_cancelar.pack(side="left", padx=5)

        self.barra_progreso = ctk.CTkProgressBar(self, width=400)
        self.barra_progreso.set(0)
        self.barra_progreso.pack(pady=(0, 10))

        self.label_estado = ctk.CTkLabel(self, text="Estado: listo")
        self.label_estado.pack(pady=10)

        self._actualizar_estado_boton_convertir()

    def _resumen_configuracion(self) -> str:
        proveedor = self.cfg.get("ocr_provider")
        etiqueta = ETIQUETAS_PROVEEDOR.get(proveedor, "-")
        if proveedor == "local":
            linea = f"OCR: {etiqueta}  ·  1 pagina por vez  ·  ~1 min c/u"
        else:
            linea = (
                f"OCR: {etiqueta}"
                f"  ·  {self.cfg.get('ocr_max_paralelo')} en paralelo"
                f"  ·  max {self.cfg.get('ocr_rpm_limite')} rpm"
            )
        segunda = (
            "Texto reformateado con IA" if self.cfg.get("estructurar_con_ia")
            else "Texto volcado tal cual (sin perdida)"
        )
        return f"{linea}\n{segunda}"

    def _actualizar_estado_boton_convertir(self):
        falta_key_ocr = not ocr.api_key_del_proveedor(self.cfg)
        # OpenRouter solo hace falta si se pidio reformatear con IA
        falta_key_estructura = bool(self.cfg.get("estructurar_con_ia")) and not self.cfg.get(
            "openrouter_api_key"
        )

        if self.pdf_path and not falta_key_ocr and not falta_key_estructura:
            self.boton_convertir.configure(state="normal")
            return

        self.boton_convertir.configure(state="disabled")
        if falta_key_ocr or falta_key_estructura:
            self.label_estado.configure(text="Estado: falta configurar API keys (ver Configuracion)")

    def _seleccionar_pdf(self):
        ruta = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if ruta:
            self.pdf_path = ruta
            self.label_archivo.configure(text=ruta.split("/")[-1].split("\\")[-1])
            self._actualizar_estado_boton_convertir()

    # --- Conversion ---

    def _iniciar_conversion(self):
        salida = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Word files", "*.docx")])
        if not salida:
            return

        self.cancelar_event = threading.Event()
        self.boton_convertir.configure(state="disabled")
        self.boton_cancelar.configure(state="normal")
        self.barra_progreso.set(0)
        # feedback inmediato: el analisis inicial puede tardar unos segundos y
        # sin esto la ventana parece congelada
        self.label_estado.configure(text="Estado: iniciando...")
        self.update_idletasks()
        hilo = threading.Thread(target=self._convertir_en_hilo, args=(salida,), daemon=True)
        hilo.start()

    def _cancelar_conversion(self):
        if self.cancelar_event is not None:
            self.cancelar_event.set()
            self.boton_cancelar.configure(state="disabled")
            self.label_estado.configure(text="Estado: cancelando (termina la pagina en curso)...")

    def _convertir_en_hilo(self, salida):
        try:
            pipeline.convertir_pdf(
                self.pdf_path, salida, self.cfg,
                progreso_callback=self._reportar_progreso,
                cancelar_event=self.cancelar_event,
            )
        except pipeline.ConversionCanceladaError:
            logger.info("Conversion cancelada por el usuario")
            self.after(0, self._mostrar_cancelado)
            return
        except (pipeline.PDFInvalidoError, OCRError, openrouter_structurer.OpenRouterError) as e:
            logger.exception("Fallo la conversion")
            self.after(0, lambda: self._mostrar_error(str(e)))
            return
        except Exception as e:
            logger.exception("Error inesperado en la conversion")
            self.after(0, lambda: self._mostrar_error(f"Error inesperado: {e}"))
            return

        self.after(0, lambda: self._mostrar_exito(salida))

    def _reportar_progreso(self, mensaje: str, fraccion: float):
        def actualizar():
            self.label_estado.configure(text=f"Estado: {mensaje}")
            self.barra_progreso.set(fraccion)

        self.after(0, actualizar)

    def _restaurar_botones(self):
        self.boton_convertir.configure(state="normal")
        self.boton_cancelar.configure(state="disabled")
        self.cancelar_event = None

    def _mostrar_error(self, mensaje: str):
        self.label_estado.configure(text="Estado: error")
        self.barra_progreso.set(0)
        self._restaurar_botones()
        messagebox.showerror("Error de conversion", mensaje)

    def _mostrar_cancelado(self):
        self.label_estado.configure(text="Estado: cancelado")
        self.barra_progreso.set(0)
        self._restaurar_botones()

    def _mostrar_exito(self, salida: str):
        self.label_estado.configure(text="Estado: listo")
        self._restaurar_botones()
        messagebox.showinfo("Exito", f"Documento guardado en:\n{salida}")

    # --- Pantalla de configuracion ---

    def _construir_pantalla_config(self):
        for widget in self.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self, text="Configuracion", font=("Segoe UI", 18, "bold")).pack(pady=(15, 10))

        contenedor = ctk.CTkScrollableFrame(self, width=470, height=320)
        contenedor.pack(padx=15, pady=(0, 10), fill="both", expand=True)

        # API keys
        ctk.CTkLabel(contenedor, text="OpenRouter API key").pack(anchor="w")
        entry_or = ctk.CTkEntry(contenedor, width=430, show="*")
        entry_or.insert(0, self.cfg.get("openrouter_api_key", ""))
        entry_or.pack(pady=(0, 10))

        ctk.CTkLabel(contenedor, text="NVIDIA API key").pack(anchor="w")
        entry_nv = ctk.CTkEntry(contenedor, width=430, show="*")
        entry_nv.insert(0, self.cfg.get("nvidia_api_key", ""))
        entry_nv.pack(pady=(0, 10))

        # Estructuracion con IA (opcional, puede perder contenido)
        var_ia = ctk.BooleanVar(value=bool(self.cfg.get("estructurar_con_ia", False)))
        ctk.CTkCheckBox(
            contenedor, text="Reformatear el texto con IA (opcional)", variable=var_ia
        ).pack(anchor="w", pady=(0, 3))
        ctk.CTkLabel(
            contenedor,
            text=(
                "Queda mas prolijo, pero el modelo puede omitir fragmentos.\n"
                "Sin tildar, el texto se vuelca tal cual: no se pierde nada."
            ),
            text_color="gray",
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        # Modelo de texto (estructuracion) - siempre OpenRouter, siempre gratuito
        ctk.CTkLabel(contenedor, text="Modelo de texto para estructurar (OpenRouter, solo gratuitos)").pack(anchor="w")
        modelo_texto_actual = self.cfg.get("openrouter_model", config.DEFAULT_CONFIG["openrouter_model"])
        combo_modelo_texto = ctk.CTkOptionMenu(contenedor, width=430, values=[modelo_texto_actual])
        combo_modelo_texto.set(modelo_texto_actual)
        combo_modelo_texto.pack(pady=(0, 3))
        label_estado_texto = ctk.CTkLabel(contenedor, text="Cargando modelos...", text_color="gray")
        label_estado_texto.pack(anchor="w", pady=(0, 10))

        # Proveedor de OCR
        ctk.CTkLabel(contenedor, text="Quien hace el OCR de las paginas escaneadas").pack(anchor="w")
        proveedor_actual = self.cfg.get("ocr_provider", "nvidia")

        hay_local = ocr.local_disponible()
        opciones = [
            etiqueta for clave, etiqueta in ETIQUETAS_PROVEEDOR.items()
            if clave != "local" or hay_local
        ]
        combo_proveedor = ctk.CTkOptionMenu(contenedor, width=430, values=opciones)
        etiqueta_actual = ETIQUETAS_PROVEEDOR.get(proveedor_actual, ETIQUETAS_PROVEEDOR["nvidia"])
        if etiqueta_actual not in opciones:
            etiqueta_actual = ETIQUETAS_PROVEEDOR["nvidia"]
        combo_proveedor.set(etiqueta_actual)
        combo_proveedor.pack(pady=(0, 3))

        if hay_local:
            aviso_local = "El modo offline no usa internet ni credenciales, pero tarda ~1 min por pagina."
        else:
            aviso_local = "El modo offline no esta instalado (falta la carpeta 'ocr-local')."
        ctk.CTkLabel(contenedor, text=aviso_local, text_color="gray").pack(anchor="w", pady=(0, 10))

        # Modelo de vision de NVIDIA
        ctk.CTkLabel(contenedor, text="Modelo de vision de NVIDIA").pack(anchor="w")
        modelo_nv_actual = self.cfg.get("nvidia_vision_model", config.DEFAULT_CONFIG["nvidia_vision_model"])
        combo_modelo_nv = ctk.CTkOptionMenu(contenedor, width=430, values=[modelo_nv_actual])
        combo_modelo_nv.set(modelo_nv_actual)
        combo_modelo_nv.pack(pady=(0, 3))
        label_estado_nv = ctk.CTkLabel(
            contenedor, text="NVIDIA no publica precios: todos usan tus creditos de la cuenta.", text_color="gray"
        )
        label_estado_nv.pack(anchor="w", pady=(0, 10))

        # Modelo de vision de OpenRouter
        ctk.CTkLabel(contenedor, text="Modelo de vision de OpenRouter (solo gratuitos)").pack(anchor="w")
        modelo_or_vision_actual = self.cfg.get(
            "openrouter_vision_model", config.DEFAULT_CONFIG["openrouter_vision_model"]
        )
        combo_modelo_or_vision = ctk.CTkOptionMenu(contenedor, width=430, values=[modelo_or_vision_actual])
        combo_modelo_or_vision.set(modelo_or_vision_actual)
        combo_modelo_or_vision.pack(pady=(0, 3))
        label_estado_or_vision = ctk.CTkLabel(contenedor, text="Cargando modelos...", text_color="gray")
        label_estado_or_vision.pack(anchor="w", pady=(0, 10))

        # Paralelismo del OCR
        ctk.CTkLabel(contenedor, text="Paginas de OCR en paralelo (1-16)").pack(anchor="w")
        entry_paralelo = ctk.CTkEntry(contenedor, width=430)
        entry_paralelo.insert(0, str(self.cfg.get("ocr_max_paralelo", config.DEFAULT_CONFIG["ocr_max_paralelo"])))
        entry_paralelo.pack(pady=(0, 10))

        ctk.CTkLabel(contenedor, text="Limite de llamadas por minuto").pack(anchor="w")
        entry_rpm = ctk.CTkEntry(contenedor, width=430)
        entry_rpm.insert(0, str(self.cfg.get("ocr_rpm_limite", config.DEFAULT_CONFIG["ocr_rpm_limite"])))
        entry_rpm.pack(pady=(0, 3))
        ctk.CTkLabel(
            contenedor,
            text="NVIDIA ronda las 40 rpm. Con los modelos free de OpenRouter conviene bajarlo.",
            text_color="gray",
        ).pack(anchor="w", pady=(0, 10))

        self._cargar_listas_de_modelos(
            combo_modelo_texto, label_estado_texto, modelo_texto_actual,
            combo_modelo_or_vision, label_estado_or_vision, modelo_or_vision_actual,
            combo_modelo_nv, label_estado_nv, modelo_nv_actual, entry_nv.get().strip(),
        )

        def guardar():
            self.cfg["openrouter_api_key"] = entry_or.get().strip()
            self.cfg["nvidia_api_key"] = entry_nv.get().strip()
            self.cfg["openrouter_model"] = combo_modelo_texto.get().strip()
            self.cfg["openrouter_vision_model"] = combo_modelo_or_vision.get().strip()
            self.cfg["nvidia_vision_model"] = combo_modelo_nv.get().strip()
            self.cfg["ocr_provider"] = PROVEEDOR_POR_ETIQUETA[combo_proveedor.get()]
            self.cfg["ocr_max_paralelo"] = entry_paralelo.get().strip()
            self.cfg["ocr_rpm_limite"] = entry_rpm.get().strip()
            self.cfg["estructurar_con_ia"] = bool(var_ia.get())
            config.save_config(self.cfg)
            # recargar aplica la validacion de rangos y descarta valores invalidos
            self.cfg = config.load_config()
            config.save_config(self.cfg)
            self._construir_pantalla_principal()

        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(pady=(0, 15))
        ctk.CTkButton(fila, text="Guardar", command=guardar).pack(side="left", padx=5)
        ctk.CTkButton(fila, text="Volver", command=self._construir_pantalla_principal).pack(side="left", padx=5)

    def _cargar_listas_de_modelos(
        self, combo_texto, label_texto, modelo_texto_actual,
        combo_or_vision, label_or_vision, modelo_or_vision_actual,
        combo_nv, label_nv, modelo_nv_actual, nvidia_api_key,
    ):
        """Consulta las listas de modelos en segundo plano para no congelar la UI."""

        def completar(combo, label, modelos, actual, texto_ok):
            if actual not in modelos:
                modelos = sorted(set(modelos) | {actual})

            def actualizar():
                combo.configure(values=modelos)
                label.configure(text=texto_ok.format(n=len(modelos)))

            self.after(0, actualizar)

        def cargar_openrouter():
            try:
                gratuitos = openrouter_models.listar_modelos_gratuitos()
                vision = openrouter_models.listar_modelos_vision_gratuitos()
            except openrouter_models.OpenRouterModelsError as e:
                logger.warning("No se pudo listar modelos de OpenRouter: %s", e)
                self.after(0, lambda: label_texto.configure(text="Sin conexion: no se actualizo la lista"))
                self.after(0, lambda: label_or_vision.configure(text="Sin conexion: no se actualizo la lista"))
                return

            completar(combo_texto, label_texto, gratuitos, modelo_texto_actual, "{n} modelos gratuitos")
            completar(
                combo_or_vision, label_or_vision, vision, modelo_or_vision_actual,
                "{n} modelos gratuitos con vision",
            )

        def cargar_nvidia():
            if not nvidia_api_key:
                self.after(0, lambda: label_nv.configure(text="Carga la API key de NVIDIA y volve a entrar aca"))
                return
            try:
                modelos = nvidia_models.listar_modelos_vision(nvidia_api_key)
            except nvidia_models.NvidiaModelsError as e:
                logger.warning("No se pudo listar modelos de NVIDIA: %s", e)
                self.after(0, lambda: label_nv.configure(text="No se pudo consultar la lista de NVIDIA"))
                return

            completar(combo_nv, label_nv, modelos, modelo_nv_actual, "{n} modelos de vision disponibles")

        threading.Thread(target=cargar_openrouter, daemon=True).start()
        threading.Thread(target=cargar_nvidia, daemon=True).start()
