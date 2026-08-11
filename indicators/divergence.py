"""
indicators/divergence.py

Responsabilidad: detectar divergencias clásicas entre el precio y el RSI
usando los dos últimos swings confirmados del mismo tipo.

Qué hace:
    - Divergencia alcista: precio hace un low más bajo, pero el RSI hace
      un low más alto (el impulso bajista se está debilitando) -> señal
      LONG.
    - Divergencia bajista: precio hace un high más alto, pero el RSI hace
      un high más bajo -> señal SHORT.
    - Devuelve ("ALCISTA"/"BAJISTA"/None, fuerza 0-100).

Qué NO hace:
    - No calcula el RSI ni los swings (depende de indicators/rsi.py vía
      la columna ya calculada, y de indicators/swings.py para localizar
      los swings).
    - No decide si esta divergencia es suficiente para abrir una posición
      (eso vive en strategies/rsi_divergence.py y en ensemble/ensemble.py).

Requiere que el DataFrame ya tenga columnas swing_high/swing_low (ver
indicators/swings.py) y la columna de RSI ya calculada (ver
indicators/rsi.py).

Migrado 1:1 desde indicators_rodri.py (rsi_divergence). Trabaja con
índices posicionales (0..n-1).
"""
import pandas as pd

from indicators.swings import last_confirmed_swing


def rsi_divergence(df: pd.DataFrame, rsi_col: str = "RSI", lookback: int = 30):
    """
    Divergencia RSI clásica entre los dos últimos swings confirmados del
    mismo tipo dentro de 'lookback' velas.
    Devuelve ("ALCISTA"/"BAJISTA"/None, fuerza 0-100).
    """
    last_pos = len(df) - 1

    pos1, low1 = last_confirmed_swing(df, "low", last_pos, lookback)
    if pos1 is not None:
        pos0, low0 = last_confirmed_swing(df, "low", pos1, lookback)
        if pos0 is not None and low1 < low0:
            rsi1 = df.iloc[pos1][rsi_col]
            rsi0 = df.iloc[pos0][rsi_col]
            if pd.notna(rsi1) and pd.notna(rsi0) and rsi1 > rsi0:
                strength = min((rsi1 - rsi0) / 20.0, 1.0) * 100.0
                return "ALCISTA", strength

    pos1, high1 = last_confirmed_swing(df, "high", last_pos, lookback)
    if pos1 is not None:
        pos0, high0 = last_confirmed_swing(df, "high", pos1, lookback)
        if pos0 is not None and high1 > high0:
            rsi1 = df.iloc[pos1][rsi_col]
            rsi0 = df.iloc[pos0][rsi_col]
            if pd.notna(rsi1) and pd.notna(rsi0) and rsi1 < rsi0:
                strength = min((rsi0 - rsi1) / 20.0, 1.0) * 100.0
                return "BAJISTA", strength

    return None, 0.0
