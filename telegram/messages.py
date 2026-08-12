"""
telegram/messages.py

Responsabilidad: construir y enviar TODOS los mensajes de negocio del bot
hacia Telegram — arranque, apertura de señal, TP1/TP2 alcanzado, cierre
de posición y resumen diario. Es el ÚNICO lugar del proyecto donde se
arma texto para Telegram.

Qué hace:
    - Helpers de formato puros: fmt_strategies, display_symbol,
      pct_from_entry.
    - Un build_*_message por cada tipo de mensaje (función pura,
      devuelve str, sin efectos secundarios) — útil para testear el
      texto sin mandar nada.
    - Un notify_* por cada tipo de mensaje (construye el texto con el
      build_* correspondiente y lo manda vía telegram/client.py).

Qué NO hace:
    - No decide CUÁNDO se dispara cada notificación (eso vive en
      engine/bot_engine.py: cuándo hay TP1, cuándo cerrar, etc.).
    - No hace ninguna petición HTTP directamente (delega siempre en
      telegram/client.py).
    - No calcula resultados de trading (is_win, r_total, was_be, etc. se
      reciben ya calculados, típicamente desde risk/risk_management.py o
      engine/bot_engine.py).

engine/bot_engine.py NUNCA debe construir un string de Telegram por su
cuenta: siempre debe llamar a una función de este archivo.

Migrado 1:1 desde bot_rodri.py (fmt_strategies, send_startup_message,
el bloque de mensaje de apertura de señal dentro de check_symbol, los
mensajes de TP1/TP2 dentro de check_symbol, el mensaje de cierre dentro
de close_position, y maybe_send_daily_summary), con una excepción
señalada explícitamente más abajo.

NOTA: context_line() existía en el original pero no se llamaba desde
ningún sitio en bot_rodri.py — se eliminó en esta migración por no
tener uso (YAGNI).

CAMBIO (acordado explícitamente): build_signal_open_message /
notify_signal_opened perdieron el parámetro 'macro_warning'. Nacía de
que el bot_rodri.py original solo AVISABA cuando la tendencia de 15m no
coincidía con la señal, pero nunca bloqueaba la apertura. Desde que
engine/bot_engine.py convirtió esa desalineación en un filtro duro que
descarta la señal ANTES de abrir posición, una señal que llega a abrirse
tiene SIEMPRE macro_aligned=True — por lo tanto el aviso nunca podía
tener contenido real en el mensaje de apertura, y mantenerlo habría sido
un parámetro muerto (YAGNI).
"""
from telegram.client import send_telegram, send_telegram_photo


# ─────────────────────────────────────────────────────────
# Helpers de formato
# ─────────────────────────────────────────────────────────

def fmt_strategies(strategies: list[str]) -> str:
    """
    Nombres de estrategia SIN guiones bajos para usar en textos con
    parse_mode="Markdown". En el Markdown "legacy" de Telegram, '_' abre y
    cierra cursiva: si el mensaje contiene un número impar de '_' (p. ej.
    una señal roja con una sola estrategia como "SMC_REVERSAL"), Telegram
    devuelve 400 ("can't find end of the entity") y el mensaje no llega.
    Ese fallo no lanza excepción en send_telegram/send_telegram_photo
    (solo se imprime), así que se pierde en silencio si no se sanea antes.
    """
    return "+".join(s.replace("_", " ") for s in strategies)


def display_symbol(symbol: str) -> str:
    return symbol.split(":")[0].replace("/", "")


def pct_from_entry(entry: float, level: float) -> str:
    if not entry:
        return ""
    pct = (level - entry) / entry * 100.0
    sign = "+" if pct >= 0 else ""
    return f" ({sign}{pct:.2f}%)"


# ─────────────────────────────────────────────────────────
# Mensaje de arranque
# ─────────────────────────────────────────────────────────

def build_startup_message(cfg, strategy_names: list[str]) -> str:
    """Mensaje de arranque con el resumen de la config activa."""
    threshold_mode = "DYNAMIC" if cfg.USE_DYNAMIC_THRESHOLD else "FIXED"
    return (
        f"🤖 Bot \"{cfg.STRATEGY_LABEL}\" iniciado.\n"
        f"Activos: {len(cfg.SYMBOLS)} | Estrategias: {', '.join(s.replace('_', ' ') for s in strategy_names)}\n"
        f"Exchange: {cfg.EXCHANGE_ID} ({cfg.MARKET_TYPE})\n"
        f"Threshold mode: {threshold_mode}\n"
        f"Escaneo: {cfg.TIMEFRAME} | Seguimiento: {cfg.MONITOR_TIMEFRAME}\n"
        f"MIN_SCORE={cfg.MIN_SCORE} | MIN_PROB={cfg.MIN_PROB}\n"
        f"Multi: max {cfg.MAX_CONCURRENT_TRADES} trades | 1 por activo | "
        f"cooldown {cfg.COOLDOWN_HOURS}h\n"
        f"Rojas: x{cfg.RED_SIZE_FACTOR}, max {cfg.RED_MAX_PER_DAY}/día, "
        f"prob≥{cfg.RED_MIN_PROB}, TP cap {cfg.RED_TP_CAP_R}R\n"
        f"Ensemble: bonus por confluencia ({cfg.CONFLUENCE_BONUS} pts/estrategia extra)"
    )


def notify_startup(cfg, strategy_names: list[str]) -> None:
    send_telegram(cfg, build_startup_message(cfg, strategy_names))


# ─────────────────────────────────────────────────────────
# Apertura de señal
# ─────────────────────────────────────────────────────────

def build_signal_open_message(cfg, symbol: str, pos: dict, last_candle_time: str) -> str:
    """
    Mensaje de apertura de señal. 'pos' debe traer: dir, entry, sl, tp1,
    tp2, tp3, tp_rr, score, prob, strategies, leverage, is_red.

    No recibe aviso de desalineación macro: una señal que llega a
    generar este mensaje ya pasó el filtro macro duro de
    engine/bot_engine.py (macro_aligned=True siempre en este punto).
    """
    direction = pos["dir"]
    emoji = "🟢" if direction == "ALCISTA" else "🔴"
    dir_label = "LONG" if direction == "ALCISTA" else "SHORT"
    sym = display_symbol(symbol)
    sl_pct = pct_from_entry(pos["entry"], pos["sl"])
    is_red = pos.get("is_red", False)
    # NOTA de migración: el original hardcodeaba el texto de la etiqueta
    # roja como " ⚠️ SEÑAL ROJA (tamaño x0.30, TP cap 1.7R)" — números
    # mágicos que duplicaban RED_SIZE_FACTOR/RED_TP_CAP_R de config. Aquí
    # se generan a partir de cfg para que no queden desincronizados si
    # cambian esos valores en config/settings.py. Con los valores por
    # defecto actuales el texto resultante es idéntico al original.
    red_tag = f" ⚠️ SEÑAL ROJA (tamaño x{cfg.RED_SIZE_FACTOR:.2f}, TP cap {cfg.RED_TP_CAP_R}R)" if is_red else ""

    return (
        f"{emoji} *{sym} | {dir_label}*{red_tag}\n"
        f"Score {pos['score']} | Prob {pos['prob'] * 100:.0f}% | {fmt_strategies(pos['strategies'])}\n\n"
        f"💰 Entrada: `{pos['entry']:.4f}`\n"
        f"🔴 Stop Loss: `{pos['sl']:.4f}`{sl_pct}\n"
        f"⚡ Apalancamiento sugerido: {pos['leverage']}x\n\n"
        f"🎯 TP1: `{pos['tp1']:.4f}`{pct_from_entry(pos['entry'], pos['tp1'])} · RR {pos['tp_rr'][0]:.2f}\n"
        f"🎯 TP2: `{pos['tp2']:.4f}`{pct_from_entry(pos['entry'], pos['tp2'])} · RR {pos['tp_rr'][1]:.2f}\n"
        f"🎯 TP3: `{pos['tp3']:.4f}`{pct_from_entry(pos['entry'], pos['tp3'])} · RR {pos['tp_rr'][2]:.2f}\n\n"
        f"⏱ {symbol} · {cfg.TIMEFRAME} · {last_candle_time}"
    )


def notify_signal_opened(cfg, symbol: str, pos: dict, last_candle_time: str,
                          chart_path: str | None = None) -> None:
    """
    Manda el mensaje de apertura de señal. Si 'chart_path' viene informado
    se manda como foto con caption; si no (p. ej. falló la generación del
    gráfico), se manda como texto plano. La decisión de generar o no el
    gráfico es responsabilidad de quien llama (engine/bot_engine.py, vía
    charting/chart_generator.py) — este módulo no sabe nada de gráficos.
    """
    msg = build_signal_open_message(cfg, symbol, pos, last_candle_time)
    if chart_path:
        send_telegram_photo(cfg, chart_path, msg)
    else:
        send_telegram(cfg, msg)


# ─────────────────────────────────────────────────────────
# TP1 / TP2 alcanzado
# ─────────────────────────────────────────────────────────

def build_tp1_message(symbol: str, tp1_price: float, be_moved: bool, entry_price: float = None) -> str:
    if be_moved:
        return (
            f"✅ *{display_symbol(symbol)}* — TP1 alcanzado (`{tp1_price:.4f}`).\n"
            f"🔒 SL movido a BE (`{entry_price:.4f}`)."
        )
    return f"✅ *{display_symbol(symbol)}* — TP1 alcanzado (`{tp1_price:.4f}`)."


def notify_tp1_hit(cfg, symbol: str, tp1_price: float, be_moved: bool, entry_price: float = None) -> None:
    send_telegram(cfg, build_tp1_message(symbol, tp1_price, be_moved, entry_price))


def build_tp2_message(symbol: str, tp2_price: float) -> str:
    return (
        f"🔥 *{display_symbol(symbol)}* — TP2 alcanzado. Runner hacia TP3.\n"
        f"`{tp2_price:.4f}`"
    )


def notify_tp2_hit(cfg, symbol: str, tp2_price: float) -> None:
    send_telegram(cfg, build_tp2_message(symbol, tp2_price))


# ─────────────────────────────────────────────────────────
# Cierre de posición
# ─────────────────────────────────────────────────────────

_CLOSE_ICON_MAP = {"flip": "🔄", "tp3": "💠", "sl_be": "🔒", "sl": "🛑"}
_CLOSE_TEXT_MAP = {
    "flip": "Flip de señal. Trade cerrado.",
    "tp3": "TP3 alcanzado. Trade cerrado.",
    "sl_be": "BE stop-out. Trade cerrado.",
    "sl": "SL alcanzado. Trade cerrado.",
}


def build_close_message(symbol: str, entry: float, last_price: float, close_reason: str,
                         was_be: bool, is_win: bool, r_total: float, extra_note: str = "") -> str:
    reason_label = "sl_be" if (close_reason == "sl" and was_be) else close_reason
    icon = _CLOSE_ICON_MAP.get(reason_label, "🛑")
    reason_text = _CLOSE_TEXT_MAP.get(reason_label, "Trade cerrado.")
    return (
        f"{icon} *{display_symbol(symbol)}* — {reason_text}{extra_note}\n"
        f"Entrada: `{entry:.4f}` | Cierre: `{last_price:.4f}`\n"
        f"Resultado: {'✅ GANADORA' if is_win else '❌ PERDEDORA'} ({r_total:+.2f}R)"
    )


def notify_position_closed(cfg, symbol: str, entry: float, last_price: float, close_reason: str,
                            was_be: bool, is_win: bool, r_total: float, extra_note: str = "") -> None:
    send_telegram(cfg, build_close_message(symbol, entry, last_price, close_reason,
                                            was_be, is_win, r_total, extra_note))


# ─────────────────────────────────────────────────────────
# Resumen diario
# ─────────────────────────────────────────────────────────

def build_daily_summary_message(cfg, stats: dict, open_positions: dict,
                                 dynamic_min_score: int, today_str: str) -> str:
    closed_trades = stats["wins"] + stats["losses"]
    win_rate = stats["wins"] / closed_trades * 100 if closed_trades else 0
    avg_r = stats["r_sum"] / closed_trades if closed_trades else 0

    open_lines = "\n".join(
        f"  • {sym}: {p['dir']} desde `{p['entry']:.4f}`"
        f"{' (ROJA)' if p.get('is_red') else ''}"
        f"{' (BE activo)' if p.get('be_active') else ''}"
        for sym, p in open_positions.items()
    ) or "  • Ninguna"

    return (
        f"[{cfg.STRATEGY_LABEL}]\n"
        f"📊 *Resumen diario* — {today_str}\n\n"
        f"*Señales:* {stats['total_signals']} "
        f"(Normales: {stats['normal_signals']} | Rojas: {stats['red_signals']}) "
        f"| Long/Short: {stats['long_signals']} / {stats['short_signals']}\n"
        f"*Cerradas:* {closed_trades} | Win rate: {win_rate:.1f}% | R medio: {avg_r:+.2f}\n"
        f"*W/L:* {stats['wins']} / {stats['losses']} | BE saves: {stats['be_saves']} | Flips: {stats['flips']}\n"
        f"*Hits:* SL {stats['sl_hits']} | TP1 {stats['tp1_hits']} | TP2 {stats['tp2_hits']} | TP3 {stats['tp3_hits']}\n"
        f"*Umbral dinámico actual:* {dynamic_min_score}\n\n"
        f"*Posiciones abiertas:*\n{open_lines}"
    )


def notify_daily_summary(cfg, stats: dict, open_positions: dict,
                          dynamic_min_score: int, today_str: str) -> None:
    send_telegram(cfg, build_daily_summary_message(cfg, stats, open_positions, dynamic_min_score, today_str))