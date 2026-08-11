"""
indicators/ema.py

Responsabilidad: calcular la Media Móvil Exponencial (EMA) sobre el precio
de cierre.

Qué hace:
    - Añade al DataFrame una columna con la EMA del cierre para el
      periodo indicado.

Qué NO hace:
    - No decide qué periodo usar (eso lo decide quien la llama, vía
      config/settings.py).
    - No calcula cruces de EMAs ni señales de trading.

Migrado 1:1 desde indicators_rodri.py (add_ema). Trabaja con índices
posicionales (0..n-1), asumiendo que el DataFrame viene con índice por
defecto (como el que devuelve fetch_ohlcv).
"""
import pandas as pd


def add_ema(df: pd.DataFrame, period: int, col_name: str) -> pd.DataFrame:
    """Media móvil exponencial."""
    df[col_name] = df["close"].ewm(span=period, adjust=False).mean()
    return df
