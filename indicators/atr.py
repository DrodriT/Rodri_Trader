"""
indicators/atr.py

Responsabilidad: calcular el Average True Range (ATR), que mide la
volatilidad reciente en unidades de precio.

Qué hace:
    - Calcula el True Range vela a vela (máximo entre high-low,
      |high-prev_close|, |low-prev_close|) y su media móvil simple.
    - Añade al DataFrame la columna resultante.

Qué NO hace:
    - No normaliza el ATR como porcentaje del precio (eso lo hace quien
      lo consuma, p. ej. risk/risk_management.py para el apalancamiento).

Migrado 1:1 desde indicators_rodri.py (add_atr). Trabaja con índices
posicionales (0..n-1).
"""
import pandas as pd


def add_atr(df: pd.DataFrame, period: int = 14, col_name: str = "ATR") -> pd.DataFrame:
    """Average True Range: mide la volatilidad reciente en unidades de precio."""
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df[col_name] = tr.rolling(window=period).mean()
    return df
