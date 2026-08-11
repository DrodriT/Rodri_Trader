"""
strategies/liquidity_grab.py

Responsabilidad: detectar la estrategia LIQUIDITY_GRAB — barrido simple
de un extremo reciente (versión más corta/rápida que SMC_REVERSAL, sin
exigir cambio de estructura).

Qué hace:
    - Compara la última vela contra el mínimo/máximo de una ventana
      corta reciente (LG_LOOKBACK velas, excluyendo la actual).
    - Si la mecha perfora ese extremo pero el cierre vuelve dentro del
      rango, genera señal en la dirección de rechazo.
    - Mira SOLO la última vela cerrada.

Qué NO hace:
    - No exige confirmación de cambio de estructura (a diferencia de
      strategies/smc_reversal.py).
    - No calcula el ATR (depende de la columna ya calculada por
      indicators/atr.py).

Migrado 1:1 desde strategy_rodri.py (detect_liquidity_grab).
"""
import pandas as pd


def detect_liquidity_grab(df: pd.DataFrame, cfg):
    """Devuelve (direction, score_parcial) para la estrategia LIQUIDITY_GRAB."""
    if len(df) < cfg.LG_LOOKBACK + 2:
        return None, 0.0
    last = df.iloc[-1]
    atr = last["ATR"]
    if pd.isna(atr) or atr == 0:
        return None, 0.0

    window = df.iloc[-(cfg.LG_LOOKBACK + 1):-1]  # excluye la vela actual
    recent_low = window["low"].min()
    recent_high = window["high"].max()

    if last["low"] < recent_low and last["close"] > recent_low:
        wick = recent_low - last["low"]
        strength = min(wick / atr, 1.5) / 1.5 * 100.0
        return "ALCISTA", strength

    if last["high"] > recent_high and last["close"] < recent_high:
        wick = last["high"] - recent_high
        strength = min(wick / atr, 1.5) / 1.5 * 100.0
        return "BAJISTA", strength

    return None, 0.0
