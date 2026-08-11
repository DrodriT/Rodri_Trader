"""
strategies/trend_pullback.py

Responsabilidad: detectar la estrategia TREND_PULLBACK — retroceso a
favor de una tendencia establecida.

Qué hace:
    - Determina tendencia (EMA rápida vs EMA lenta + ADX mínimo).
    - En uptrend: si la vela anterior tocó/perforó la EMA rápida
      (retroceso) y la última vela cierra de nuevo por encima, en verde
      -> señal de continuación alcista.
    - Análogo simétrico para downtrend.
    - Mira SOLO la última vela cerrada (y la anterior, para el retroceso).

Qué NO hace:
    - No calcula EMA ni ADX (dependen de columnas ya calculadas por
      indicators/ema.py e indicators/adx.py).

Migrado 1:1 desde strategy_rodri.py (detect_trend_pullback).
"""
import pandas as pd


def detect_trend_pullback(df: pd.DataFrame, cfg):
    """Devuelve (direction, score_parcial) para la estrategia TREND_PULLBACK."""
    if len(df) < 3:
        return None, 0.0
    last = df.iloc[-1]
    prev = df.iloc[-2]
    ema_fast_col = f"EMA{cfg.EMA_FAST}"
    ema_slow_col = f"EMA{cfg.EMA_SLOW}"
    adx = last["ADX"]
    if pd.isna(adx) or pd.isna(last[ema_fast_col]) or pd.isna(prev[ema_fast_col]):
        return None, 0.0

    is_uptrend = last[ema_fast_col] > last[ema_slow_col] and adx >= cfg.TREND_ADX_MIN
    is_downtrend = last[ema_fast_col] < last[ema_slow_col] and adx >= cfg.TREND_ADX_MIN

    # Uptrend: la vela anterior tocó/perforó la EMA rápida (retroceso) y la
    # última vela cierra de nuevo por encima, en verde -> continuación.
    if (is_uptrend and prev["low"] <= prev[ema_fast_col]
            and last["close"] > last[ema_fast_col] and last["close"] > last["open"]):
        strength = min(adx / 50.0, 1.0) * 100.0
        return "ALCISTA", strength

    if (is_downtrend and prev["high"] >= prev[ema_fast_col]
            and last["close"] < last[ema_fast_col] and last["close"] < last["open"]):
        strength = min(adx / 50.0, 1.0) * 100.0
        return "BAJISTA", strength

    return None, 0.0
