"""
storage/state_store.py

Responsabilidad: persistencia del estado del bot (posiciones abiertas,
cooldowns, contador de señales rojas, resultados recientes, threshold
dinámico, trade_log, stats, etc.) en disco.

Qué hace:
    - default_state: la forma inicial del estado, cuando no existe
      todavía ningún archivo de estado.
    - load_state: carga el estado desde STATE_FILE si existe (rellenando
      con default_state cualquier clave que falte, por compatibilidad
      hacia adelante si se añaden claves nuevas), o devuelve
      default_state si el archivo no existe todavía.
    - save_state: escribe el estado completo a STATE_FILE.

Qué NO hace:
    - No decide QUÉ va dentro del estado en cada momento (eso lo decide
      engine/bot_engine.py: abrir/cerrar posiciones, actualizar
      cooldowns, etc. — aquí solo se lee/escribe lo que ya viene armado).
    - No conoce el formato de ningún campo del trade_log en detalle más
      allá de que es serializable a JSON.
    - El resto del proyecto (engine/, analytics/) no sabe que el estado
      se guarda en JSON — solo llama a load_state/save_state. Si en el
      futuro se migra a otra persistencia (p. ej. SQLite), solo este
      archivo cambia.

Migrado 1:1 desde bot_rodri.py (default_state, load_state, save_state).
'cfg' se recibe explícito en vez de importar config/settings.py a nivel
de módulo, por consistencia con el resto del proyecto.
"""
import json
import os


def default_state(cfg) -> dict:
    """Estado inicial del bot, usado cuando todavía no existe STATE_FILE."""
    return {
        "positions": {},
        "cooldowns": {},
        "red_signals_today": {"date": None, "count": 0},
        "recent_results": [],
        "dynamic_min_score": cfg.MIN_SCORE,
        "trade_log": [],
        "stats": {},
        "last_daily_summary_date": None,
        "startup_notified": False,
    }


def load_state(cfg) -> dict:
    """
    Carga el estado desde cfg.STATE_FILE. Si el archivo existe, rellena
    con default_state() cualquier clave que falte (compatibilidad hacia
    adelante). Si no existe, devuelve default_state() directamente.
    """
    if os.path.exists(cfg.STATE_FILE):
        with open(cfg.STATE_FILE, "r") as f:
            state = json.load(f)
        for k, v in default_state(cfg).items():
            state.setdefault(k, v)
        return state
    return default_state(cfg)


def save_state(state: dict, cfg) -> None:
    """Escribe el estado completo a cfg.STATE_FILE."""
    with open(cfg.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
