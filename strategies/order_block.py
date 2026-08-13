"""
strategies/order_block.py

Responsabilidad: detectar la estrategia ORDER_BLOCK — vela opuesta
(Order Block) que origina un impulso estructural, validada por un Fair
Value Gap (FVG) contenido en su rango.

Qué hace:
    - Exige, sobre la última vela cerrada (vela de impulso):
        1. Impulso: la vela cierra en la dirección de la señal y su
           rango (high-low) supera OB_IMPULSE_ATR_MULT x ATR.
        2. Ruptura de estructura: el cierre de la vela de impulso supera
           el último swing high/low confirmado (buscado con OB_LOOKBACK).
        3. Vela Order Block: la vela de color opuesto más reciente,
           buscada hacia atrás hasta OB_CANDLE_SEARCH velas.
        4. FVG: existe un Fair Value Gap en las 3 últimas velas
           (indicators/fvg.py) y su zona queda COMPLETAMENTE contenida
           dentro del rango de la vela Order Block.
    - Mira SOLO la última vela cerrada (aunque para localizar la vela
      Order Block y el swing roto consulta velas anteriores, igual que
      SMC_REVERSAL consulta swings previos).

Qué NO hace:
    - No calcula el ATR ni localiza los swings (depende de
      indicators/atr.py e indicators/swings.py).
    - No calcula el FVG (depende de indicators/fvg.py).
    - No decide si esta señal es suficiente para operar (eso lo hace
      ensemble/ensemble.py).

Migrado 1:1 desde strategy_rodri.py (detect_order_block, tras el diseño
acordado: vela de impulso = última vela cerrada; vela OB buscada hasta
OB_CANDLE_SEARCH velas atrás; FVG siempre en las 3 últimas velas,
exigiendo contención estricta dentro de la vela OB; sin espera de
mitigación).
"""
import pandas as pd

from indicators.fvg import detect_fvg
from indicators.swings import last_confirmed_swing


def _find_opposite_candle(df: pd.DataFrame, last_pos: int, search_n: int, bearish: bool):
    """
    Busca hacia atrás, desde 'last_pos - 1' hasta 'last_pos - search_n'
    (inclusive), la vela más reciente cuyo color sea el opuesto al
    impulso: 'bearish=True' busca la última vela bajista (close < open,
    candidata a Order Block alcista); 'bearish=False' busca la última
    vela alcista (candidata a Order Block bajista). Devuelve la posición
    encontrada o None si no hay ninguna en la ventana.
    """
    start = max(0, last_pos - search_n)
    for pos in range(last_pos - 1, start - 1, -1):
        candle = df.iloc[pos]
        if pd.isna(candle["open"]) or pd.isna(candle["close"]):
            continue
        if bearish and candle["close"] < candle["open"]:
            return pos
        if not bearish and candle["close"] > candle["open"]:
            return pos
    return None


def _order_block_strength(impulse_range: float, atr: float, cfg, fvg: dict) -> float:
    """
    Fuerza 0-100 combinando dos componentes, cada uno capado a 50 puntos:
      - cuánto supera el impulso al umbral OB_IMPULSE_ATR_MULT (en ATR).
      - cuán grande es la zona del FVG relativa al ATR.
    """
    impulse_excess = max(impulse_range / atr - cfg.OB_IMPULSE_ATR_MULT, 0.0)
    impulse_score = min(impulse_excess / cfg.OB_IMPULSE_ATR_MULT, 1.0) * 50.0

    fvg_size = fvg["zone_high"] - fvg["zone_low"]
    fvg_score = min(fvg_size / atr, 1.0) * 50.0

    return min(100.0, impulse_score + fvg_score)


def detect_order_block(df: pd.DataFrame, cfg):
    """Devuelve (direction, score_parcial) para la estrategia ORDER_BLOCK."""
    last_pos = len(df) - 1
    if last_pos < 2:
        return None, 0.0

    last = df.iloc[last_pos]
    atr = last["ATR"]
    if pd.isna(atr) or atr == 0:
        return None, 0.0

    impulse_range = last["high"] - last["low"]
    impulse_ok = impulse_range >= cfg.OB_IMPULSE_ATR_MULT * atr
    is_bullish_impulse = last["close"] > last["open"]
    is_bearish_impulse = last["close"] < last["open"]

    fvg = detect_fvg(df, last_pos)

    # Caso ALCISTA: impulso alcista + FVG alcista contenido en una vela
    # bajista previa (Order Block) + ruptura del último swing high.
    if is_bullish_impulse and impulse_ok and fvg and fvg["direction"] == "ALCISTA":
        _, swing_high_price = last_confirmed_swing(df, "high", last_pos, cfg.OB_LOOKBACK)
        if swing_high_price is not None and last["close"] > swing_high_price:
            ob_pos = _find_opposite_candle(df, last_pos, cfg.OB_CANDLE_SEARCH, bearish=True)
            if ob_pos is not None:
                ob_low = df.iloc[ob_pos]["low"]
                ob_high = df.iloc[ob_pos]["high"]
                if fvg["zone_low"] >= ob_low and fvg["zone_high"] <= ob_high:
                    return "ALCISTA", _order_block_strength(impulse_range, atr, cfg, fvg)

    # Caso BAJISTA: simétrico.
    if is_bearish_impulse and impulse_ok and fvg and fvg["direction"] == "BAJISTA":
        _, swing_low_price = last_confirmed_swing(df, "low", last_pos, cfg.OB_LOOKBACK)
        if swing_low_price is not None and last["close"] < swing_low_price:
            ob_pos = _find_opposite_candle(df, last_pos, cfg.OB_CANDLE_SEARCH, bearish=False)
            if ob_pos is not None:
                ob_low = df.iloc[ob_pos]["low"]
                ob_high = df.iloc[ob_pos]["high"]
                if fvg["zone_low"] >= ob_low and fvg["zone_high"] <= ob_high:
                    return "BAJISTA", _order_block_strength(impulse_range, atr, cfg, fvg)

    return None, 0.0