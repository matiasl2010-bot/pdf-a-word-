import sys
import os
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rate_limiter import RateLimiter


def test_permite_llamadas_bajo_el_limite_sin_esperar():
    limiter = RateLimiter(max_llamadas=5, ventana_segundos=1.0)

    inicio = time.monotonic()
    for _ in range(5):
        limiter.esperar_turno()
    transcurrido = time.monotonic() - inicio

    assert transcurrido < 0.2


def test_bloquea_cuando_se_supera_el_limite():
    limiter = RateLimiter(max_llamadas=2, ventana_segundos=0.4)

    inicio = time.monotonic()
    for _ in range(3):
        limiter.esperar_turno()
    transcurrido = time.monotonic() - inicio

    # la 3ra llamada tiene que esperar a que salga de la ventana la 1ra
    assert transcurrido >= 0.35


def test_libera_turnos_al_pasar_la_ventana():
    limiter = RateLimiter(max_llamadas=2, ventana_segundos=0.3)

    limiter.esperar_turno()
    limiter.esperar_turno()
    time.sleep(0.35)

    inicio = time.monotonic()
    limiter.esperar_turno()
    transcurrido = time.monotonic() - inicio

    assert transcurrido < 0.1


def test_es_seguro_entre_hilos():
    limiter = RateLimiter(max_llamadas=4, ventana_segundos=0.5)
    turnos = []
    lock = threading.Lock()

    def trabajo():
        limiter.esperar_turno()
        with lock:
            turnos.append(time.monotonic())

    hilos = [threading.Thread(target=trabajo) for _ in range(8)]
    inicio = time.monotonic()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert len(turnos) == 8
    # los primeros 4 entran ya; los otros 4 esperan a la siguiente ventana
    assert time.monotonic() - inicio >= 0.45


def test_max_llamadas_cero_o_negativo_no_limita():
    limiter = RateLimiter(max_llamadas=0, ventana_segundos=60)

    inicio = time.monotonic()
    for _ in range(10):
        limiter.esperar_turno()

    assert time.monotonic() - inicio < 0.2
