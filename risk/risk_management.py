"""
risk/risk_management.py

Responsabilidad: todo el cálculo de gestión de riesgo del bot — niveles
de SL/TP, capado de TP para señales rojas, apalancamiento sugerido según
volatilidad, y el threshold dinámico de score según rachas de resultados.

Qué hace:
    - build_risk_levels: calcula SL y TP1/TP2/TP3 según un preset de
      riesgo (config.RISK_PRESETS).
    - cap_tp_at_r: recalcula los TP de una señal roja para que ningún RR
      supere un cap dado, manteniendo el mismo SL.
    - suggest_leverage: apalancamiento sugerido según volatilidad
      relativa (ATR% sobre precio).
    - update_dynamic_threshold: sube/baja el score mínimo dinámico según
      rachas de pérdidas/ganancias recientes.
    - register_result: añade un resultado (ganó/perdió) al historial
      reciente usado por update_dynamic_threshold.

Qué NO hace:
    - No decide si una señal concreta es "normal"/"roja"/"descartada"
      (eso vive en filters/signal_quality_filter.py, aún por migrar).
    - No persiste el estado en disco (state se recibe y se muta en
      memoria; guardar en disco es responsabilidad de
      storage/state_store.py).
    - No calcula indicadores (ATR viene ya calculado en el DataFrame por
      indicators/atr.py).

Nota de diseño: a diferencia del bot_rodri.py original (que importaba
config_rodri como módulo global), update_dynamic_threshold y
register_result reciben aquí 'cfg' como parámetro explícito, igual que
el resto de funciones del proyecto — así risk/ no depende de un import
fijo de config/settings.py y es más fácil de probar de forma aislada.
El comportamiento numérico es idéntico al original.

Migrado 1:1 (con la salvedad de cfg explícito) desde strategy_rodri.py
(build_risk_levels, cap_tp_at_r, suggest_leverage) y bot_rodri.py
(update_dynamic_threshold, register_result).
"""
import pandas as pd


def build_risk_levels(entry_price: float, atr_val: float, signal_type: str, preset: str, cfg):
    """
    Calcula SL y TP1/TP2/TP3 según el preset de riesgo elegido.
    SL = entry -/+ (sl_mult × ATR). TP_n = entry +/- (tp_mult_n × distancia_SL).
    """
    preset_cfg = cfg.RISK_PRESETS[preset]
    is_long = signal_type == "ALCISTA"
    sl_distance = atr_val * preset_cfg["sl_mult"]

    sl = entry_price - sl_distance if is_long else entry_price + sl_distance
    tps = []
    for i, mult in enumerate(preset_cfg["tp_mults"], start=1):
        tp_price = entry_price + sl_distance * mult if is_long else entry_price - sl_distance * mult
        tps.append({"label": f"TP{i}", "price": tp_price, "rr": mult})

    return {"sl": sl, "sl_distance": sl_distance, "tps": tps}


def cap_tp_at_r(risk: dict, entry_price: float, signal_type: str, cap_rr: float) -> dict:
    """
    Para señales "rojas": recalcula los TP para que ningún RR supere
    cap_rr (ej. 1.7R), manteniendo el mismo SL/sl_distance.
    """
    is_long = signal_type == "ALCISTA"
    sl_distance = risk["sl_distance"]
    capped_tps = []
    for tp in risk["tps"]:
        rr = min(tp["rr"], cap_rr)
        price = entry_price + sl_distance * rr if is_long else entry_price - sl_distance * rr
        capped_tps.append({"label": tp["label"], "price": price, "rr": rr})
    new_risk = dict(risk)
    new_risk["tps"] = capped_tps
    return new_risk


def suggest_leverage(df: pd.DataFrame, cfg) -> int:
    """
    Apalancamiento sugerido según volatilidad relativa (ATR% sobre precio):
    más volátil -> leverage más bajo. Interpolación lineal invertida entre
    LEVERAGE_MAX (a ATR% <= LEV_ATR_PCT_LOW) y LEVERAGE_MIN (a ATR% >=
    LEV_ATR_PCT_HIGH).
    """
    last = df.iloc[-1]
    if not last["close"] or pd.isna(last["ATR"]):
        return cfg.LEVERAGE_MIN
    atr_pct = (last["ATR"] / last["close"]) * 100.0
    lo, hi = cfg.LEV_ATR_PCT_LOW, cfg.LEV_ATR_PCT_HIGH

    if atr_pct <= lo:
        lev = cfg.LEVERAGE_MAX
    elif atr_pct >= hi:
        lev = cfg.LEVERAGE_MIN
    else:
        t = (atr_pct - lo) / (hi - lo)
        lev = cfg.LEVERAGE_MAX - t * (cfg.LEVERAGE_MAX - cfg.LEVERAGE_MIN)

    return int(round(lev))


def update_dynamic_threshold(state: dict, cfg) -> None:
    """
    Sube o baja state['dynamic_min_score'] según las rachas de resultados
    recientes (state['recent_results']). Muta 'state' en memoria.
    """
    if not cfg.USE_DYNAMIC_THRESHOLD:
        state["dynamic_min_score"] = cfg.MIN_SCORE
        return

    current = state.get("dynamic_min_score", cfg.MIN_SCORE)
    results = state.get("recent_results", [])

    if len(results) >= cfg.DYNAMIC_LOSING_STREAK_TO_RAISE:
        if all(r is False for r in results[-cfg.DYNAMIC_LOSING_STREAK_TO_RAISE:]):
            current = min(cfg.DYNAMIC_THRESHOLD_MAX, current + cfg.DYNAMIC_THRESHOLD_STEP)

    if len(results) >= cfg.DYNAMIC_WINNING_STREAK_TO_LOWER:
        if all(r is True for r in results[-cfg.DYNAMIC_WINNING_STREAK_TO_LOWER:]):
            current = max(cfg.DYNAMIC_THRESHOLD_MIN, current - cfg.DYNAMIC_THRESHOLD_STEP)

    state["dynamic_min_score"] = current


def register_result(state: dict, is_win: bool, cfg) -> None:
    """
    Añade un resultado (True=ganó, False=perdió) al historial reciente
    usado por update_dynamic_threshold. Muta 'state' en memoria.
    """
    results = state.setdefault("recent_results", [])
    results.append(bool(is_win))
    if len(results) > cfg.DYNAMIC_THRESHOLD_LOOKBACK_TRADES:
        del results[0]
