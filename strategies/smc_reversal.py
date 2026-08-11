"""
strategies/smc_reversal.py

Responsabilidad: detectar la estrategia SMC_REVERSAL — barrido de
liquidez (swing sweep) con cambio de estructura (CHoCH simplificado).

Qué hace:
    - Barrido alcista: mecha por debajo del último swing low confirmado,
      pero cierre de vuelta por encima de ese nivel (vela de rechazo).
      Si además el cierre supera el swing high previo a ese swing low,
      se considera confirmación de cambio de estructura y se bonifica
      la fuerza de la señal.
    - Barrido bajista: análogo, simétrico.
    - Mira SOLO la última vela cerrada.

Qué NO hace:
    - No calcula el ATR ni localiza los swings (depende de
      indicators/atr.py e indicators/swings.py mediante columnas/función
      ya calculadas).
    - No decide si esta señal es suficiente para operar (eso lo hace
      ensemble/ensemble.py).

Migrado 1:1 desde strategy_rodri.py (detect_smc_reversal).
"""
import pandas as pd

from indicators.swings import last_confirmed_swing


def detect_smc_reversal(df: pd.DataFrame, cfg):
    """Devuelve (direction, score_parcial) para la estrategia SMC_REVERSAL."""
    last = df.iloc[-1]
    last_pos = len(df) - 1
    atr = last["ATR"]
    if pd.isna(atr) or atr == 0:
        return None, 0.0

    # Barrido alcista: mecha por debajo del último swing low confirmado,
    # pero cierre de vuelta por encima de ese nivel (vela de rechazo).
    pos_low, swing_low_price = last_confirmed_swing(df, "low", last_pos, cfg.SMC_LOOKBACK)
    if (pos_low is not None and last["low"] < swing_low_price
            and last["close"] > swing_low_price and last["close"] > last["open"]):
        # Confirmación de cambio de estructura (CHoCH simplificado): el
        # cierre supera el swing high previo a ese swing low.
        _, swing_high_price = last_confirmed_swing(df, "high", pos_low, cfg.SMC_LOOKBACK)
        structure_shift = swing_high_price is not None and last["close"] > swing_high_price
        wick = swing_low_price - last["low"]
        strength = min(wick / atr, 2.0) / 2.0 * 100.0
        if structure_shift:
            strength = min(100.0, strength + 20.0)
        return "ALCISTA", strength

    # Barrido bajista simétrico
    pos_high, swing_high_price = last_confirmed_swing(df, "high", last_pos, cfg.SMC_LOOKBACK)
    if (pos_high is not None and last["high"] > swing_high_price
            and last["close"] < swing_high_price and last["close"] < last["open"]):
        _, swing_low_price2 = last_confirmed_swing(df, "low", pos_high, cfg.SMC_LOOKBACK)
        structure_shift = swing_low_price2 is not None and last["close"] < swing_low_price2
        wick = last["high"] - swing_high_price
        strength = min(wick / atr, 2.0) / 2.0 * 100.0
        if structure_shift:
            strength = min(100.0, strength + 20.0)
        return "BAJISTA", strength

    return None, 0.0
