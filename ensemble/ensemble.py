"""
ensemble/ensemble.py

Responsabilidad: combinar los resultados de las 6 estrategias
(strategies/registry.py) en una única señal de ensemble, con su score
final y su probabilidad heurística asociada.

Qué hace:
    - score_to_probability: transforma un score 0-100 en una probabilidad
      heurística 0-1 (interpolación lineal entre PROB_AT_SCORE_0 y
      PROB_AT_SCORE_100).
    - compute_ensemble_signal:
        1. Ejecuta las 6 estrategias (run_all_strategies).
        2. Agrupa los hits por dirección (ALCISTA / BAJISTA).
        3. Si ambas direcciones dispararon a la vez, gana la de mayor
           score combinado.
        4. score_final:
             - Con 1 sola estrategia (sin confluencia): su score parcial
               ponderado por su peso (STRATEGY_WEIGHTS), capado a
               MAX_SOLO_SCORE: min(score_parcial * peso/100, MAX_SOLO_SCORE).
             - Con 2+ estrategias (confluencia): promedio PONDERADO de
               los scores parciales por el peso de cada estrategia,
               + CONFLUENCE_BONUS por cada estrategia extra de acuerdo
               (el bonus de confluencia no lleva peso, es un bonus plano
               por nº de estrategias). Capado a 100.
        5. Deriva la probabilidad del score final.
      Devuelve None si no hay ninguna señal, o un dict con toda la info.

Qué NO hace:
    - No decide si la señal es "normal", "roja" o "descartada" (eso vive
      en filters/signal_quality_filter.py, aún por migrar).
    - No conoce la lógica interna de ninguna estrategia individual (solo
      usa la lista de hits que devuelve strategies/registry.py).

IMPORTANTE: la "Prob" que calcula score_to_probability es una
transformación heurística del score, NO una probabilidad estadística
basada en backtest — no existe ese modelo. Ajustar
PROB_AT_SCORE_0/PROB_AT_SCORE_100 en config/settings.py si más adelante
se calibra con resultados reales.

NOTA sobre pesos: cfg.STRATEGY_WEIGHTS se expresa en % (100 = peso
normal/neutro). Con todos los pesos en 100 el resultado es idéntico al
promedio simple sin pesos (comportamiento original de
strategy_rodri.py). El promedio se mantiene siempre en escala 0-100 pase
lo que pase con los pesos, para no romper MIN_SCORE, el threshold
dinámico, MAX_SOLO_SCORE ni score_to_probability, que dependen de esa
escala.
"""
import pandas as pd

from strategies.registry import run_all_strategies


def score_to_probability(score: float, cfg) -> float:
    """
    Transformación heurística score -> probabilidad. Lineal entre
    PROB_AT_SCORE_0 y PROB_AT_SCORE_100.
    """
    p0, p100 = cfg.PROB_AT_SCORE_0, cfg.PROB_AT_SCORE_100
    prob = p0 + (score / 100.0) * (p100 - p0)
    return max(0.0, min(1.0, prob))


def compute_ensemble_signal(df: pd.DataFrame, cfg):
    """
    Combina las 6 estrategias y devuelve None si no hay señal, o un dict:
        {
            "direction": "ALCISTA" | "BAJISTA",
            "score": int,
            "prob": float,
            "strategies": [nombre, ...],
            "confluence": int,
        }
    """
    hits = run_all_strategies(df, cfg)
    if not hits:
        return None

    by_dir = {"ALCISTA": [], "BAJISTA": []}
    for h in hits:
        by_dir[h["direction"]].append(h)

    def weight_of(strategy_name: str) -> float:
        # Peso en % (100 = neutro). Si una estrategia no está en
        # STRATEGY_WEIGHTS, se asume peso neutro (100) para no romper el
        # ensemble por una entrada de config olvidada.
        return cfg.STRATEGY_WEIGHTS.get(strategy_name, 100) / 100.0

    def dir_total(hs):
        if not hs:
            return -1.0
        if len(hs) == 1:
            # Sin confluencia: se pondera por el peso de la única
            # estrategia y se capa el score — ninguna estrategia sola
            # puede alcanzar el máximo (evita falsa sensación de "Score
            # 100" cuando en realidad solo hay UNA señal detrás, sin
            # confirmación de ninguna otra).
            weighted_solo = hs[0]["score"] * weight_of(hs[0]["name"])
            return min(weighted_solo, cfg.MAX_SOLO_SCORE)
        # Con confluencia: promedio PONDERADO por el peso de cada
        # estrategia (no un promedio simple), + bonus plano de
        # confluencia (el bonus no lleva peso).
        weighted_sum = sum(h["score"] * weight_of(h["name"]) for h in hs)
        weight_sum = sum(weight_of(h["name"]) for h in hs)
        avg = weighted_sum / weight_sum if weight_sum > 0 else 0.0
        bonus = cfg.CONFLUENCE_BONUS * (len(hs) - 1)
        return min(100.0, avg + bonus)

    total_long = dir_total(by_dir["ALCISTA"])
    total_short = dir_total(by_dir["BAJISTA"])

    if total_long < 0 and total_short < 0:
        return None

    if total_long >= total_short:
        winning_dir, winning_hits, score = "ALCISTA", by_dir["ALCISTA"], total_long
    else:
        winning_dir, winning_hits, score = "BAJISTA", by_dir["BAJISTA"], total_short

    score = round(score)
    prob = round(score_to_probability(score, cfg), 2)

    return {
        "direction": winning_dir,
        "score": score,
        "prob": prob,
        "strategies": [h["name"] for h in winning_hits],
        "confluence": len(winning_hits),
    }
