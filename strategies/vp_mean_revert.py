"""
strategies/vp_mean_revert.py

Responsabilidad: detectar la estrategia VP_MEAN_REVERT — reversión hacia
el POC (Point of Control) del Volume Profile cuando el precio sale de la
Value Area.

Qué hace:
    - Construye el Volume Profile de la ventana reciente (VP_LOOKBACK
      velas, VP_BINS bins).
    - Si el cierre está por debajo del VAL -> señal ALCISTA (reversión
      hacia el POC).
    - Si el cierre está por encima del VAH -> señal BAJISTA.
    - Mira SOLO la última vela cerrada.

Qué NO hace:
    - No calcula el Volume Profile en sí (delega en
      indicators/volume_profile.py).
    - No calcula el ATR (depende de la columna ya calculada por
      indicators/atr.py).

Migrado 1:1 desde strategy_rodri.py (detect_vp_mean_revert).
"""
import pandas as pd

from indicators.volume_profile import add_volume_profile


def detect_vp_mean_revert(df: pd.DataFrame, cfg):
    """Devuelve (direction, score_parcial) para la estrategia VP_MEAN_REVERT."""
    if len(df) < cfg.VP_LOOKBACK:
        return None, 0.0
    last = df.iloc[-1]
    atr = last["ATR"]
    if pd.isna(atr) or atr == 0:
        return None, 0.0

    vp = add_volume_profile(df, cfg.VP_LOOKBACK, cfg.VP_BINS)
    if vp is None:
        return None, 0.0

    if last["close"] < vp["val"]:
        dist = vp["poc"] - last["close"]
        strength = min(dist / atr, 3.0) / 3.0 * 100.0
        return "ALCISTA", strength

    if last["close"] > vp["vah"]:
        dist = last["close"] - vp["poc"]
        strength = min(dist / atr, 3.0) / 3.0 * 100.0
        return "BAJISTA", strength

    return None, 0.0
