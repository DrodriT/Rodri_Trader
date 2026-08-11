"""
strategies/rsi_divergence.py

Responsabilidad: adaptar la detección de divergencias RSI (indicators/
divergence.py) a la interfaz común de estrategia (df, cfg) -> (direction,
score_parcial).

Qué hace:
    - Delega directamente en indicators.divergence.rsi_divergence, usando
      la ventana DIVERGENCE_LOOKBACK de la configuración.

Qué NO hace:
    - No calcula el RSI ni localiza los swings (eso vive en
      indicators/rsi.py e indicators/swings.py).

Migrado 1:1 desde strategy_rodri.py (detect_rsi_divergence).
"""
import pandas as pd

from indicators.divergence import rsi_divergence


def detect_rsi_divergence(df: pd.DataFrame, cfg):
    """Devuelve (direction, score_parcial) para la estrategia RSI_DIVERGENCE."""
    return rsi_divergence(df, "RSI", cfg.DIVERGENCE_LOOKBACK)
