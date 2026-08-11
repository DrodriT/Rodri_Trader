"""
engine/bot_engine.py

Responsabilidad: orquestar todo el ciclo de vida del bot por símbolo —
detectar señal, decidir su calidad, abrir/cerrar posiciones, monitorizar
SL/TP, gestionar cooldowns y señales rojas, actualizar estadísticas, y
disparar las notificaciones de Telegram correspondientes.

Qué hace:
    - compute_base_indicators: aplica los indicadores compartidos al
      DataFrame antes de correr las estrategias.
    - get_stats / classify_closed_position / classify_signal_quality:
      lógica de clasificación de resultados y calidad de señal.
    - Cooldown y señales rojas: is_in_cooldown, set_cooldown,
      can_open_new_trade, red_signals_used_today, register_red_signal.
    - check_higher_timeframe_trend: filtro macro (EMA 200 en 15m).
    - close_position: cierra una posición, registra stats/resultado y
      notifica por Telegram.
    - check_symbol: el orquestador por símbolo (señal -> apertura ->
      monitorización de SL/TP).
    - run_once: una pasada completa sobre todos los símbolos.
    - maybe_send_daily_summary / notify_startup_once.

Qué NO hace:
    - No construye NINGÚN texto de Telegram directamente (siempre delega
      en telegram/messages.py).
    - No calcula indicadores individuales, estrategias, niveles de
      riesgo ni el score del ensemble (delega en indicators/,
      strategies/, ensemble/ y risk/).
    - No decide cómo se persiste el estado (delega en
      storage/state_store.py).
    - No hace peticiones HTTP al exchange directamente más allá de
      exchange/market_data.py.

CORRECCIONES DE COMPORTAMIENTO respecto al bot_rodri.py original
(acordadas explícitamente antes de implementar este módulo):

  Bug 1 — Ambigüedad SL/TP en la misma vela: si en una misma vela de 1m
  se tocan SL y un TP no alcanzado todavía, SIEMPRE gana el SL (caso
  conservador). El código original ya evitaba marcar tp_reached en ese
  caso gracias al guard 'and not sl_hit', pero aquí se hace explícito y
  se preserva también al recorrer varias velas en el mismo ciclo (ver
  Bug 2).

  Bug 2 — Huecos de monitorización: en vez de mirar solo la última vela
  de 1m en cada ejecución, se calcula cuánto tiempo pasó desde la última
  vela ya monitorizada (o desde la vela de entrada, si es la primera
  vez) y se piden con exchange/market_data.fetch_ohlcv suficientes velas
  de 1m para cubrir ese hueco (tope de seguridad: cfg.MAX_MONITOR_CANDLES
  velas). Se recorren en orden cronológico, aplicando el criterio del
  Bug 1 vela a vela, deteniéndose en cuanto la posición se cierra.
  LIMITACIÓN CONOCIDA: si el hueco es mayor a MAX_MONITOR_CANDLES
  minutos (p. ej. el bot estuvo caído varios días), no se puede cubrir
  el hueco completo — es un tope de seguridad deliberado para no pedir
  miles de velas de golpe.

DESVIACIÓN DE DISEÑO (no es un bug del original, es un cambio de
comportamiento acordado explícitamente): en bot_rodri.py, macro_aligned
=False solo añadía un aviso en el mensaje de Telegram, nunca bloqueaba
la entrada. Aquí se convierte en un filtro duro: si la tendencia macro
(EMA200 en HIGHER_TIMEFRAME) no coincide con la dirección de la señal,
la señal se descarta ANTES de clasificar su calidad — se aplica por
igual a señales normales y rojas. NEUTRAL (precio sin cruce claro de la
EMA200) sigue contando como alineado, igual que en el original.
CONSECUENCIA DE COSTE: check_higher_timeframe_trend() pasa de llamarse
solo al abrir una posición a llamarse en cada ciclo en que haya señal
del ensemble (incluso si acaba descartándose), porque ahora hace falta
conocerla ANTES de decidir si la señal es accionable.

NOTA (no es uno de los bugs acordados, se preserva 1:1): al cerrar una
posición por SL/TP/flip, el precio de "exit" que se registra en el
trade_log es el último cierre del timeframe de señales (5m), NO el
precio exacto de SL/TP que disparó el cierre en el timeframe de
monitorización (1m). Esto ya era así en el bot_rodri.py original.

Migrado desde bot_rodri.py: get_stats, check_higher_timeframe_trend,
is_in_cooldown, set_cooldown, can_open_new_trade, _red_tracker,
red_signals_used_today, register_red_signal, classify_closed_position,
classify_signal_quality, close_position, check_symbol, run_once,
maybe_send_daily_summary, notify_startup_once. compute_base_indicators
viene de strategy_rodri.py (quedó huérfana tras dividir strategies/ y
ensemble/, se ubica aquí por ser preparación de datos previa a correr
las estrategias dentro de check_symbol).
"""
from datetime import datetime, timezone, timedelta

import pandas as pd

from indicators.atr import add_atr
from indicators.ema import add_ema
from indicators.adx import add_adx
from indicators.rsi import add_rsi
from indicators.volume_ratio import add_volume_ratio
from indicators.swings import add_swings
from strategies.registry import STRATEGY_NAMES
from ensemble.ensemble import compute_ensemble_signal
from risk.risk_management import (
    build_risk_levels, cap_tp_at_r, suggest_leverage,
    update_dynamic_threshold, register_result,
)
from exchange.market_data import create_exchange, fetch_ohlcv
from charting.chart_generator import generate_signal_chart
from storage.state_store import load_state, save_state
from telegram import messages as tg


# ══════════════════════════════════════════════════════════
# Preparación de datos
# ══════════════════════════════════════════════════════════

def compute_base_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Indicadores compartidos que necesitan varias de las 6 estrategias."""
    df = add_atr(df, cfg.ATR_LEN, col_name="ATR")
    df = add_ema(df, cfg.EMA_FAST, col_name=f"EMA{cfg.EMA_FAST}")
    df = add_ema(df, cfg.EMA_SLOW, col_name=f"EMA{cfg.EMA_SLOW}")
    df = add_adx(df, cfg.ADX_PERIOD)
    df = add_rsi(df, cfg.RSI_PERIOD)
    df = add_volume_ratio(df, cfg.VOLUME_MA_PERIOD)
    df = add_swings(df, cfg.SWING_LEFT, cfg.SWING_RIGHT)
    return df


# ══════════════════════════════════════════════════════════
# Estadísticas
# ══════════════════════════════════════════════════════════

def get_stats(state: dict) -> dict:
    stats = state.setdefault("stats", {})
    defaults = {
        "total_signals": 0, "normal_signals": 0, "red_signals": 0,
        "long_signals": 0, "short_signals": 0,
        "sl_hits": 0, "tp1_hits": 0, "tp2_hits": 0, "tp3_hits": 0,
        "flips": 0, "wins": 0, "losses": 0, "be_saves": 0, "r_sum": 0.0,
    }
    for k, v in defaults.items():
        stats.setdefault(k, v)
    return stats


# ══════════════════════════════════════════════════════════
# Filtro macro (15m)
# ══════════════════════════════════════════════════════════

def check_higher_timeframe_trend(exchange, symbol: str, cfg) -> str:
    """
    Obtiene velas de 15m y evalúa si el precio está por encima/debajo de
    la EMA 200. Retorna: 'ALCISTA', 'BAJISTA' o 'NEUTRAL'.
    """
    try:
        limit = cfg.MACRO_EMA_PERIOD + 20
        df_15m = fetch_ohlcv(exchange, symbol, cfg.HIGHER_TIMEFRAME, limit)
        df_15m["ema_macro"] = df_15m["close"].ewm(span=cfg.MACRO_EMA_PERIOD, adjust=False).mean()

        last_close = df_15m.iloc[-1]["close"]
        last_ema = df_15m.iloc[-1]["ema_macro"]

        if last_close > last_ema:
            return "ALCISTA"
        elif last_close < last_ema:
            return "BAJISTA"
    except Exception as e:
        print(f"[ERROR Filtro Macro 15m] {symbol}: {e}")

    return "NEUTRAL"


def is_macro_aligned(macro_trend: str, signal_direction: str) -> bool:
    """
    NEUTRAL cuenta como alineado (no bloquea), igual que en el bot_rodri.py
    original. Solo bloquea una tendencia macro EXPLÍCITAMENTE contraria a
    la dirección de la señal.
    """
    return macro_trend == "NEUTRAL" or macro_trend == signal_direction


# ══════════════════════════════════════════════════════════
# Cooldown / límites de posiciones / señales rojas
# ══════════════════════════════════════════════════════════

def is_in_cooldown(state: dict, symbol: str, now: datetime) -> bool:
    until = state.get("cooldowns", {}).get(symbol)
    return bool(until) and now < datetime.fromisoformat(until)


def set_cooldown(state: dict, symbol: str, now: datetime, cfg) -> None:
    until = now + timedelta(hours=cfg.COOLDOWN_HOURS)
    state.setdefault("cooldowns", {})[symbol] = until.isoformat()


def can_open_new_trade(state: dict, symbol: str, now: datetime, cfg) -> bool:
    if is_in_cooldown(state, symbol, now):
        return False
    positions = state.get("positions", {})
    if symbol in positions:
        return False
    if len(positions) >= cfg.MAX_CONCURRENT_TRADES:
        return False
    return True


def _red_tracker(state: dict, now: datetime) -> dict:
    today_str = now.strftime("%Y-%m-%d")
    tracker = state.setdefault("red_signals_today", {"date": None, "count": 0})
    if tracker["date"] != today_str:
        tracker["date"] = today_str
        tracker["count"] = 0
    return tracker


def red_signals_used_today(state: dict, now: datetime) -> int:
    return _red_tracker(state, now)["count"]


def register_red_signal(state: dict, now: datetime) -> None:
    _red_tracker(state, now)["count"] += 1


# ══════════════════════════════════════════════════════════
# Clasificación de operación cerrada / calidad de señal
# ══════════════════════════════════════════════════════════

def classify_closed_position(pos: dict, close_reason: str, was_be_at_start: bool):
    if pos.get("tp1_reached"):
        r1 = (1 / 3) * pos["tp_rr"][0]
        r2 = (1 / 3) * pos["tp_rr"][1] if pos.get("tp2_reached") else 0.0
        r3 = (1 / 3) * pos["tp_rr"][2] if pos.get("tp3_reached") else 0.0
        r_total = (r1 + r2 + r3) * pos.get("size_factor", 1.0)
        is_win = True
        is_be_save = close_reason == "sl" and was_be_at_start
    else:
        r_total = -1.0 * pos.get("size_factor", 1.0)
        is_win = False
        is_be_save = False
    return is_win, is_be_save, r_total


def classify_signal_quality(signal: dict, dynamic_min_score: int, cfg) -> str:
    """
    Devuelve 'normal', 'roja' o 'descartada'. Una señal solo puede ser
    'normal' (tamaño completo) si además de superar el score/prob
    mínimos, tiene confluencia de varias estrategias
    (MIN_CONFLUENCE_FOR_NORMAL). Con una sola estrategia disparando, como
    mucho se trata como 'roja'.

    NOTA: el filtro macro (is_macro_aligned) se aplica ANTES de llamar a
    esta función, en check_symbol — si la señal no está alineada con la
    tendencia macro, se descarta directamente sin llegar aquí.
    """
    has_confluence = signal["confluence"] >= cfg.MIN_CONFLUENCE_FOR_NORMAL
    if has_confluence and signal["score"] >= dynamic_min_score and signal["prob"] >= cfg.MIN_PROB:
        return "normal"
    if signal["prob"] >= cfg.RED_MIN_PROB:
        return "roja"
    return "descartada"


# ══════════════════════════════════════════════════════════
# Cierre de posición
# ══════════════════════════════════════════════════════════

def close_position(state: dict, symbol: str, pos: dict, last_price: float,
                    close_reason: str, now: datetime, cfg, extra_note: str = "") -> None:
    """Cierra una posición: registra stats, resultado, cooldown y avisa por Telegram."""
    stats = get_stats(state)
    was_be = pos.get("be_active", False)
    is_win, is_be_save, r_total = classify_closed_position(pos, close_reason, was_be)
    stats["wins" if is_win else "losses"] += 1
    stats["be_saves"] += 1 if is_be_save else 0
    stats["r_sum"] += r_total
    if close_reason == "flip":
        stats["flips"] += 1
    register_result(state, is_win, cfg)

    reason_label = "sl_be" if (close_reason == "sl" and was_be) else close_reason

    tg.notify_position_closed(cfg, symbol, pos["entry"], last_price, close_reason,
                               was_be, is_win, r_total, extra_note)

    state.setdefault("positions", {}).pop(symbol, None)
    set_cooldown(state, symbol, now, cfg)
    state.pop(f"{symbol}_last_monitored_candle", None)

    log = state.setdefault("trade_log", [])
    log.append({
        "symbol": symbol,
        "dir": pos["dir"],
        "strategies": pos["strategies"],
        "confluence": pos["confluence"],
        "score": pos["score"],
        "prob": pos["prob"],
        "is_red": pos.get("is_red", False),
        "leverage": pos.get("leverage"),
        "entry": pos["entry"],
        "exit": last_price,
        "r_result": round(r_total, 4),
        "is_win": is_win,
        "close_reason": reason_label,
        "entry_candle": pos["entry_candle"],
        "closed_at": now.isoformat(),
    })
    if len(log) > cfg.TRADE_LOG_MAX:
        del log[:len(log) - cfg.TRADE_LOG_MAX]


# ══════════════════════════════════════════════════════════
# Lógica principal por símbolo
# ══════════════════════════════════════════════════════════

def check_symbol(exchange, symbol: str, state: dict, now: datetime, cfg) -> None:
    limit = max(cfg.VP_LOOKBACK, cfg.SMC_LOOKBACK, cfg.BREAKOUT_LOOKBACK) + 100
    df = fetch_ohlcv(exchange, symbol, cfg.TIMEFRAME, limit)
    df = compute_base_indicators(df, cfg)

    last_candle_time = df.iloc[-1]["datetime"].isoformat()
    last_price = df.iloc[-1]["close"]

    positions = state.setdefault("positions", {})
    stats = get_stats(state)
    pos = positions.get(symbol)

    last_processed_key = f"{symbol}_last_processed_candle"
    already_processed_this_candle = state.get(last_processed_key) == last_candle_time

    # ── 1. Señal ensemble sobre la última vela cerrada ──
    signal = None if already_processed_this_candle else compute_ensemble_signal(df, cfg)

    quality = None
    macro_trend = None
    macro_aligned = True
    if signal:
        # Filtro macro (15m): se evalúa ANTES de clasificar la calidad de
        # la señal. Si no está alineada, se descarta aquí mismo — se
        # aplica por igual a lo que habría sido señal normal o roja
        # (decisión acordada explícitamente, ver docstring del módulo).
        macro_trend = check_higher_timeframe_trend(exchange, symbol, cfg)
        macro_aligned = is_macro_aligned(macro_trend, signal["direction"])

        if not macro_aligned:
            quality = "descartada"
        else:
            dynamic_min_score = state.get("dynamic_min_score", cfg.MIN_SCORE)
            quality = classify_signal_quality(signal, dynamic_min_score, cfg)
            if quality == "roja" and red_signals_used_today(state, now) >= cfg.RED_MAX_PER_DAY:
                quality = "descartada"  # límite diario de señales rojas alcanzado

    actionable_signal = signal is not None and quality in ("normal", "roja")

    # ── 2. Flip: señal contraria mientras hay posición abierta -> cerrar antes ──
    if actionable_signal and pos and pos["dir"] != signal["direction"]:
        close_position(state, symbol, pos, last_price, "flip", now, cfg)
        pos = None

    # ── 3. Abrir nueva posición si hay hueco y no hay ya una en este símbolo ──
    if actionable_signal and not pos and can_open_new_trade(state, symbol, now, cfg):
        atr_val = df.iloc[-1]["ATR"]
        risk = build_risk_levels(last_price, atr_val, signal["direction"], cfg.RISK_PRESET, cfg)
        is_red = quality == "roja"
        if is_red:
            risk = cap_tp_at_r(risk, last_price, signal["direction"], cfg.RED_TP_CAP_R)
            register_red_signal(state, now)

        leverage = suggest_leverage(df, cfg)

        # macro_trend/macro_aligned ya se calcularon en el paso 1. Aquí
        # macro_aligned es siempre True: si hubiera sido False, la señal
        # se habría marcado "descartada" y no se habría llegado a este
        # bloque. Ya no existe un "aviso macro" que mostrar en el mensaje
        # de apertura, porque una señal desalineada nunca llega a abrirse.

        new_pos = {
            "dir": signal["direction"],
            "entry": last_price,
            "entry_candle": last_candle_time,
            "sl": risk["sl"],
            "tp1": risk["tps"][0]["price"], "tp2": risk["tps"][1]["price"], "tp3": risk["tps"][2]["price"],
            "tp_rr": [tp["rr"] for tp in risk["tps"]],
            "tp1_reached": False, "tp2_reached": False, "tp3_reached": False,
            "be_active": False,
            "score": signal["score"], "prob": signal["prob"],
            "strategies": signal["strategies"], "confluence": signal["confluence"],
            "leverage": leverage,
            "is_red": is_red,
            "size_factor": cfg.RED_SIZE_FACTOR if is_red else 1.0,
            "macro_trend": macro_trend,
            "macro_aligned": macro_aligned,
        }
        positions[symbol] = new_pos
        pos = new_pos

        stats["total_signals"] += 1
        stats["red_signals" if is_red else "normal_signals"] += 1
        stats["long_signals" if signal["direction"] == "ALCISTA" else "short_signals"] += 1

        chart_path = None
        try:
            chart_path = generate_signal_chart(
                df, symbol, signal["direction"], pos["score"], pos["prob"],
                pos["strategies"], pos["entry"], pos["sl"],
                [pos["tp1"], pos["tp2"], pos["tp3"]],
                lookback_candles=cfg.CHART_LOOKBACK_CANDLES,
            )
        except Exception as e:
            print(f"[ERROR gráfico] {e}")
            chart_path = None

        tg.notify_signal_opened(cfg, symbol, pos, "", last_candle_time, chart_path=chart_path)
        console_msg = tg.build_signal_open_message(cfg, symbol, pos, "", last_candle_time)
        print(console_msg.replace("*", "").replace("`", ""))

    # ── 4. Comprobar hits de SL/TP en timeframe de seguimiento (1m) ──
    if pos:
        is_entry_candle = pos["entry_candle"] == last_candle_time
        if not is_entry_candle:
            _monitor_position(exchange, symbol, pos, state, stats, last_price, now, cfg)

    state[last_processed_key] = last_candle_time


def _monitor_position(exchange, symbol: str, pos: dict, state: dict, stats: dict,
                       last_price: float, now: datetime, cfg) -> None:
    """
    Recorre todas las velas de 1m nuevas desde la última monitorizada (o
    desde la vela de entrada, si es la primera vez) y comprueba hits de
    SL/TP vela a vela, en orden cronológico, aplicando el criterio de que
    el SL siempre gana si se toca junto a un TP no alcanzado todavía en
    la misma vela (Bug 1). Se detiene en cuanto la posición se cierra.
    """
    watermark_key = f"{symbol}_last_monitored_candle"
    watermark_str = state.get(watermark_key)
    entry_dt = pd.to_datetime(pos["entry_candle"])
    since_dt = pd.to_datetime(watermark_str) if watermark_str else entry_dt

    elapsed_minutes = max((now - since_dt.to_pydatetime()).total_seconds() / 60.0, 1)
    limit = int(min(elapsed_minutes + 2, cfg.MAX_MONITOR_CANDLES))
    limit = max(limit, 3)  # nunca menos de 3, como el comportamiento original

    df_mon = fetch_ohlcv(exchange, symbol, cfg.MONITOR_TIMEFRAME, limit)
    new_candles = df_mon[df_mon["datetime"] > since_dt]
    if new_candles.empty:
        new_candles = df_mon.tail(1)

    is_long = pos["dir"] == "ALCISTA"
    last_monitored_dt = since_dt
    position_closed = False

    for _, mon_candle in new_candles.iterrows():
        mon_high, mon_low = mon_candle["high"], mon_candle["low"]

        sl_hit = (mon_low <= pos["sl"]) if is_long else (mon_high >= pos["sl"])
        tp1_hit = (mon_high >= pos["tp1"]) if is_long else (mon_low <= pos["tp1"])
        tp2_hit = (mon_high >= pos["tp2"]) if is_long else (mon_low <= pos["tp2"])
        tp3_hit = (mon_high >= pos["tp3"]) if is_long else (mon_low <= pos["tp3"])

        # Bug 1: el SL siempre gana si se toca junto a un TP no alcanzado
        # todavía dentro de la misma vela.
        tp1_first = tp1_hit and not pos["tp1_reached"] and not sl_hit
        tp2_first = tp2_hit and not pos["tp2_reached"] and not sl_hit
        tp3_first = tp3_hit and not pos["tp3_reached"] and not sl_hit

        if tp1_first:
            pos["tp1_reached"] = True
            stats["tp1_hits"] += 1
            if cfg.USE_BREAK_EVEN and not pos["be_active"]:
                pos["sl"] = pos["entry"]
                pos["be_active"] = True
                tg.notify_tp1_hit(cfg, symbol, pos["tp1"], be_moved=True, entry_price=pos["entry"])
            else:
                tg.notify_tp1_hit(cfg, symbol, pos["tp1"], be_moved=False)

        if tp2_first:
            pos["tp2_reached"] = True
            stats["tp2_hits"] += 1
            tg.notify_tp2_hit(cfg, symbol, pos["tp2"])

        if sl_hit or tp3_first:
            if tp3_first:
                pos["tp3_reached"] = True
                stats["tp3_hits"] += 1
                close_position(state, symbol, pos, last_price, "tp3", now, cfg)
            else:
                stats["sl_hits"] += 1
                close_position(state, symbol, pos, last_price, "sl", now, cfg)
            position_closed = True
            break

        last_monitored_dt = mon_candle["datetime"]

    if not position_closed:
        state[watermark_key] = last_monitored_dt.isoformat()
    # Si se cerró, close_position() ya limpió watermark_key.


# ══════════════════════════════════════════════════════════
# Resumen diario / arranque
# ══════════════════════════════════════════════════════════

def maybe_send_daily_summary(state: dict, cfg) -> None:
    if not cfg.SEND_DAILY_SUMMARY:
        return

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    if now.hour < cfg.DAILY_SUMMARY_HOUR_UTC:
        return
    if state.get("last_daily_summary_date") == today_str:
        return

    stats = get_stats(state)
    open_positions = state.get("positions", {})
    dynamic_min_score = state.get("dynamic_min_score", cfg.MIN_SCORE)

    tg.notify_daily_summary(cfg, stats, open_positions, dynamic_min_score, today_str)
    state["last_daily_summary_date"] = today_str


def notify_startup_once(cfg) -> None:
    """
    Manda el mensaje de arranque (resumen de config) solo la primera vez
    que el bot corre — se recuerda en el estado persistido, así que en
    modo --once (GitHub Actions, un proceso nuevo cada vez) no se repite
    en cada ejecución programada.
    """
    state = load_state(cfg)
    if not state.get("startup_notified"):
        tg.notify_startup(cfg, STRATEGY_NAMES)
        state["startup_notified"] = True
        save_state(state, cfg)


# ══════════════════════════════════════════════════════════
# Bucle principal (una pasada)
# ══════════════════════════════════════════════════════════

def run_once(cfg) -> None:
    exchange = create_exchange(cfg)
    state = load_state(cfg)
    now = datetime.now(timezone.utc)

    update_dynamic_threshold(state, cfg)

    for symbol in cfg.SYMBOLS:
        try:
            check_symbol(exchange, symbol, state, now, cfg)
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")

    maybe_send_daily_summary(state, cfg)
    save_state(state, cfg)