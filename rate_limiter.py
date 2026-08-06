"""Limitador de llamadas por ventana de tiempo (rate limit).

Necesario para paralelizar el OCR sin pasarse del limite de la API: NVIDIA NIM
permite del orden de 40 requests por minuto, y OpenRouter es mas restrictivo aun
en los modelos gratuitos."""

import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_llamadas: int, ventana_segundos: float = 60.0):
        self.max_llamadas = max_llamadas
        self.ventana_segundos = ventana_segundos
        self._marcas = deque()
        self._lock = threading.Lock()

    def esperar_turno(self) -> None:
        """Bloquea hasta que se pueda hacer una llamada mas sin superar el limite."""
        if self.max_llamadas <= 0:
            return

        while True:
            with self._lock:
                ahora = time.monotonic()
                while self._marcas and ahora - self._marcas[0] >= self.ventana_segundos:
                    self._marcas.popleft()

                if len(self._marcas) < self.max_llamadas:
                    self._marcas.append(ahora)
                    return

                espera = self.ventana_segundos - (ahora - self._marcas[0])

            time.sleep(max(espera, 0.01))
