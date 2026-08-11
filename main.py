"""
main.py

Responsabilidad: entrypoint del bot "Rodri v1.0". Arranca el bot, manda
el aviso de arranque una sola vez, y corre el bucle principal — una sola
pasada (--once, para GitHub Actions) o en bucle continuo (uso local).

Qué hace:
    - Imprime un log de arranque con la config activa.
    - Llama a engine.bot_engine.notify_startup_once (recuerda en el
      estado persistido si ya se avisó, para no repetirlo en cada
      ejecución --once).
    - Si se pasa --once: ejecuta engine.bot_engine.run_once una sola vez
      y termina.
    - Si no: corre run_once en bucle, esperando
      config.CHECK_INTERVAL_SECONDS entre pasadas.

Qué NO hace:
    - No contiene lógica de trading, indicadores, estrategias ni
      notificaciones — todo eso vive en los módulos correspondientes
      (engine/, strategies/, telegram/, etc.). Este archivo solo arranca
      y programa las ejecuciones.

Uso:
    python3 main.py            # corre en bucle
    python3 main.py --once     # ejecuta una sola pasada (GitHub Actions)

Migrado 1:1 desde bot_rodri.py (main, y el bloque if __name__ == "__main__").
"""
import sys
import time
from datetime import datetime, timezone

import config.settings as config
from engine.bot_engine import run_once, notify_startup_once


def main() -> None:
    print(f"[{config.STRATEGY_LABEL}] Bot iniciado {datetime.now(timezone.utc).isoformat()} | "
          f"Símbolos: {config.SYMBOLS} | Timeframe: {config.TIMEFRAME}")
    notify_startup_once(config)

    if "--once" in sys.argv:
        run_once(config)
        return

    while True:
        run_once(config)
        time.sleep(config.CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
