"""
strategies/breakout.py

Responsabilidad: detectar la estrategia BREAKOUT — ruptura de rango con
confirmación de volumen.

Qué hace:
    - Calcula el rango (máximo/mínimo) de una ventana reciente
      (BREAKOUT_LOOKBACK velas, excluyendo la actual).
    - Si el cierre rompe ese rango, combina la distancia de ruptura
      (en ATR) con el ratio de volumen para formar la fuerza de la señal.
    - Mira SOLO la última vela cerrada.

Qué NO hace:
    - No calcula el ATR ni el ratio de volumen (dependen de columnas ya
      calculadas por indicators/atr.py e indicators/volume_ratio.py).

Migrado 1:1 desde strategy_rodri.py (detect_breakout).
"""
import pandas as pd


def detect_breakout(df: pd.DataFrame, cfg):
    """Devuelve (direction, score_parcial) para la estrategia BREAKOUT."""
    if len(df) < cfg.BREAKOUT_LOOKBACK + 2:
        return None, 0.0
    last = df.iloc[-1]
    atr = last["ATR"]
    if pd.isna(atr) or atr == 0:
        return None, 0.0

    window = df.iloc[-(cfg.BREAKOUT_LOOKBACK + 1):-1]
    range_high = window["high"].max()
    range_low = window["low"].min()
    vol_ratio = last["VOL_RATIO"] if pd.notna(last["VOL_RATIO"]) else 1.0

    if last["close"] > range_high:
        break_dist = last["close"] - range_high
        strength = min(break_dist / atr, 1.5) / 1.5 * 60.0
        strength += min(vol_ratio / cfg.BREAKOUT_VOL_THRESHOLD, 1.0) * 40.0
        return "ALCISTA", min(strength, 100.0)

    if last["close"] < range_low:
        break_dist = range_low - last["close"]
        strength = min(break_dist / atr, 1.5) / 1.5 * 60.0
        strength += min(vol_ratio / cfg.BREAKOUT_VOL_THRESHOLD, 1.0) * 40.0
        return "BAJISTA", min(strength, 100.0)

    return None, 0.0
