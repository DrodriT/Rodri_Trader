"""
indicators/adx.py

Responsabilidad: calcular el Average Directional Index (ADX) junto con
+DI y -DI, suavizado a la Wilder.

Qué hace:
    - Calcula +DM/-DM, el True Range suavizado (Wilder), +DI/-DI, el DX y
      finalmente el ADX.
    - Añade tres columnas al DataFrame: {prefix}, {prefix}_plusDI,
      {prefix}_minusDI.

Qué NO hace:
    - No decide el umbral de "tendencia establecida" (eso vive en
      strategies/trend_pullback.py, vía config.TREND_ADX_MIN).

Migrado 1:1 desde indicators_rodri.py (add_adx). Trabaja con índices
posicionales (0..n-1).
"""
import pandas as pd


def add_adx(df: pd.DataFrame, period: int = 14, prefix: str = "ADX") -> pd.DataFrame:
    """Average Directional Index (con +DI y -DI), suavizado a la Wilder."""
    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move

    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr_wilder = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_wilder
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_wilder

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    df[prefix] = adx
    df[f"{prefix}_plusDI"] = plus_di
    df[f"{prefix}_minusDI"] = minus_di
    return df
