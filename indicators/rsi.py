"""
indicators/rsi.py

Responsabilidad: calcular el Relative Strength Index (RSI) clásico, con
el suavizado de Wilder.

Qué hace:
    - Calcula ganancias/pérdidas medias suavizadas (EWM con alpha=1/period)
      y deriva el RSI 0-100.
    - Trata el caso de pérdida media cero como RSI=100.

Qué NO hace:
    - No detecta divergencias (eso vive en indicators/divergence.py).
    - No decide el periodo (viene de config/settings.py).

Migrado 1:1 desde indicators_rodri.py (add_rsi). Trabaja con índices
posicionales (0..n-1).
"""
import pandas as pd


def add_rsi(df: pd.DataFrame, period: int = 14, col_name: str = "RSI") -> pd.DataFrame:
    """Relative Strength Index clásico (suavizado de Wilder)."""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    df[col_name] = 100 - (100 / (1 + rs))
    df.loc[avg_loss == 0, col_name] = 100
    return df
