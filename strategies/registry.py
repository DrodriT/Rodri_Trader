"""
strategies/registry.py

Responsabilidad: mantener el registro único de las estrategias
disponibles y ejecutarlas todas sobre la última vela cerrada.

Qué hace:
    - STRATEGY_NAMES: lista ordenada con los nombres de las 7 estrategias.
    - DETECTORS: mapa nombre -> función detect_* correspondiente.
    - run_all_strategies: ejecuta las 7 estrategias y devuelve solo las
      que dispararon señal.

Qué NO hace:
    - No combina las señales en un ensemble ni calcula el score final
      (eso vive en ensemble/ensemble.py).
    - No conoce la lógica interna de ninguna estrategia (solo importa su
      función pública).

Es el único punto del proyecto que conoce la lista completa de
estrategias: añadir una estrategia nueva significa crear su archivo en
strategies/ y añadir una línea aquí, sin tocar ensemble/ ni engine/.

Migrado 1:1 desde strategy_rodri.py (STRATEGY_NAMES, DETECTORS,
run_all_strategies), con ORDER_BLOCK añadida como 7ª estrategia.
"""
import pandas as pd

from strategies.smc_reversal import detect_smc_reversal
from strategies.breakout import detect_breakout
from strategies.trend_pullback import detect_trend_pullback
from strategies.rsi_divergence import detect_rsi_divergence
from strategies.vp_mean_revert import detect_vp_mean_revert
from strategies.liquidity_grab import detect_liquidity_grab
from strategies.order_block import detect_order_block

STRATEGY_NAMES = [
    "SMC_REVERSAL", "BREAKOUT", "TREND_PULLBACK",
    "RSI_DIVERGENCE", "VP_MEAN_REVERT", "LIQUIDITY_GRAB", "ORDER_BLOCK",
]

DETECTORS = {
    "SMC_REVERSAL": detect_smc_reversal,
    "BREAKOUT": detect_breakout,
    "TREND_PULLBACK": detect_trend_pullback,
    "RSI_DIVERGENCE": detect_rsi_divergence,
    "VP_MEAN_REVERT": detect_vp_mean_revert,
    "LIQUIDITY_GRAB": detect_liquidity_grab,
    "ORDER_BLOCK": detect_order_block,
}


def run_all_strategies(df: pd.DataFrame, cfg) -> list[dict]:
    """
    Ejecuta las 7 estrategias sobre la última vela cerrada.
    Devuelve una lista de dicts {"name", "direction", "score"} — solo las
    que efectivamente dispararon señal.
    """
    hits = []
    for name, fn in DETECTORS.items():
        direction, score = fn(df, cfg)
        if direction:
            hits.append({"name": name, "direction": direction, "score": round(score, 1)})
    return hits