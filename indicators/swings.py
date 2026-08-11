"""
indicators/swings.py

Responsabilidad: detectar fractales de swing (swing high / swing low) y
localizar el último swing confirmado antes de una posición dada.

Qué hace:
    - add_swings: marca cada vela como swing high/low si su high/low es
      el extremo dentro de una ventana [i-left, i+right].
    - last_confirmed_swing: busca hacia atrás, desde una posición dada,
      el último swing confirmado de un tipo ("high" o "low").

Qué NO hace:
    - No decide qué hacer con el swing encontrado (barridos de liquidez,
      CHoCH, etc. viven en las estrategias que los consumen, p. ej.
      strategies/smc_reversal.py y strategies/liquidity_grab.py).
    - Las últimas 'right' velas nunca pueden confirmarse todavía (haría
      falta ver velas futuras), así que quedan en False — es el
      comportamiento correcto: un swing solo cuenta cuando ya está
      confirmado por el precio posterior.

Migrado 1:1 desde indicators_rodri.py (add_swings, last_confirmed_swing).
Trabaja con índices posicionales (0..n-1).
"""
import numpy as np
import pandas as pd


def add_swings(df: pd.DataFrame, left: int = 3, right: int = 3,
                high_col: str = "swing_high", low_col: str = "swing_low") -> pd.DataFrame:
    """
    Marca fractales de swing: una vela es swing high si su high es el máximo
    entre 'left' velas antes y 'right' velas después (y análogo para swing
    low).
    """
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    is_high = np.zeros(n, dtype=bool)
    is_low = np.zeros(n, dtype=bool)

    for i in range(left, n - right):
        window_h = highs[i - left:i + right + 1]
        window_l = lows[i - left:i + right + 1]
        if highs[i] == window_h.max():
            is_high[i] = True
        if lows[i] == window_l.min():
            is_low[i] = True

    df[high_col] = is_high
    df[low_col] = is_low
    return df


def last_confirmed_swing(df: pd.DataFrame, kind: str, before_pos: int, lookback: int = 200):
    """
    Devuelve (posición, precio) del último swing confirmado de tipo 'high' o
    'low' ANTES de la posición 'before_pos' (sin incluirla), buscando hacia
    atrás hasta 'lookback' velas. Devuelve (None, None) si no encuentra nada.
    """
    col = "swing_high" if kind == "high" else "swing_low"
    price_col = "high" if kind == "high" else "low"
    start = max(0, before_pos - lookback)
    if before_pos <= start:
        return None, None
    sub = df.iloc[start:before_pos]
    matches_pos = np.where(sub[col].values)[0]
    if len(matches_pos) == 0:
        return None, None
    pos = start + matches_pos[-1]
    return pos, df.iloc[pos][price_col]
