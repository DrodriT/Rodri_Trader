"""
indicators/volume_ratio.py

Responsabilidad: calcular el ratio entre el volumen de la vela actual y
la media de volumen de las velas anteriores.

Qué hace:
    - Calcula la media móvil de volumen (excluyendo la vela actual, vía
      shift(1)) y el ratio volumen_actual / media.
    - Añade ambas columnas al DataFrame (la media y el ratio).

Qué NO hace:
    - No decide el umbral de "volumen alto" (eso vive en
      strategies/breakout.py, vía config.BREAKOUT_VOL_THRESHOLD).

Migrado 1:1 desde indicators_rodri.py (add_volume_ratio). Trabaja con
índices posicionales (0..n-1).
"""
import pandas as pd


def add_volume_ratio(df: pd.DataFrame, period: int = 20, col_name: str = "VOL_RATIO",
                      ma_col_name: str = "VOL_MA") -> pd.DataFrame:
    """Ratio entre el volumen actual y la media de las 'period' velas anteriores."""
    avg_volume = df["volume"].shift(1).rolling(window=period).mean()
    df[ma_col_name] = avg_volume
    df[col_name] = df["volume"] / avg_volume
    return df
