"""
config/settings.py

Responsabilidad: centralizar toda la configuración del bot "Rodri v1.0".

Qué hace:
    - Carga credenciales sensibles (Telegram) desde variables de entorno
      (soporta un archivo .env local vía python-dotenv si está presente).
    - Expone como constantes de módulo todos los parámetros de: exchange,
      símbolos, timeframes, indicadores, estrategias, ensemble/score,
      umbrales, gestión de posiciones, riesgo/apalancamiento, gráfico y
      persistencia.

Qué NO hace:
    - No valida los valores (p. ej. no comprueba que TELEGRAM_TOKEN sea
      válido).
    - No contiene lógica de negocio ni de trading.
    - No se conecta a ningún servicio externo.

Migrado 1:1 desde config_rodri.py: mismos nombres, mismos valores, para
que el resto de módulos lo importen sin cambiar ninguna referencia
(`from config import settings` y luego `settings.SYMBOLS`, etc.).
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv es opcional: si no está instalado, simplemente se
    # confía en las variables de entorno ya presentes en el sistema.
    pass


# ─────────────────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.environ.get("TELEGRAM_TOKEN", "PON_AQUI_TU_TOKEN")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "PON_AQUI_TU_CHAT_ID")


# ─────────────────────────────────────────────────────────
# Exchange
# ─────────────────────────────────────────────────────────
EXCHANGE_ID: str = "bitget"
MARKET_TYPE: str = "swap"   # perpetuos


# ─────────────────────────────────────────────────────────
# Símbolos a vigilar (formato ccxt para perpetuos con margen USDT)
# ─────────────────────────────────────────────────────────
SYMBOLS: list[str] = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "BCH/USDT:USDT",
    "SUI/USDT:USDT",
    "XLM/USDT:USDT",
    "INJ/USDT:USDT",
    "HBAR/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "LTC/USDT:USDT",
    "AAVE/USDT:USDT",
    "ICP/USDT:USDT",
    "OP/USDT:USDT",
    "NEAR/USDT:USDT",
    "XMR/USDT:USDT",
    "DOGE/USDT:USDT",
]


# ─────────────────────────────────────────────────────────
# Timeframes
# ─────────────────────────────────────────────────────────
TIMEFRAME: str = "5m"            # escaneo de señales (detección del ensemble)
HIGHER_TIMEFRAME: str = "15m"    # filtro macro de tendencia (confirmación)
MONITOR_TIMEFRAME: str = "1m"    # seguimiento de SL/TP de posiciones abiertas
MAX_MONITOR_CANDLES: int = 200   # tope de velas de 1m a pedir de golpe al recuperar
                                  # un hueco de monitorización (evita pedir miles de
                                  # velas si el bot estuvo caído mucho tiempo)


# ─────────────────────────────────────────────────────────
# Filtro Macro
# ─────────────────────────────────────────────────────────
MACRO_EMA_PERIOD: int = 200      # periodo de la EMA para tendencia macro (15m)


# ─────────────────────────────────────────────────────────
# Indicadores base compartidos
# ─────────────────────────────────────────────────────────
ATR_LEN: int = 14
EMA_FAST: int = 20
EMA_SLOW: int = 50
ADX_PERIOD: int = 14
RSI_PERIOD: int = 14
VOLUME_MA_PERIOD: int = 20
SWING_LEFT: int = 3              # velas a cada lado para confirmar un fractal/swing
SWING_RIGHT: int = 3


# ─────────────────────────────────────────────────────────
# Parámetros específicos por estrategia
# ─────────────────────────────────────────────────────────
SMC_LOOKBACK: int = 50           # velas hacia atrás para buscar el swing a barrer
LG_LOOKBACK: int = 20            # ventana corta para LIQUIDITY_GRAB
BREAKOUT_LOOKBACK: int = 30      # ventana del rango para BREAKOUT
BREAKOUT_VOL_THRESHOLD: float = 1.3
TREND_ADX_MIN: int = 20          # ADX mínimo para considerar "tendencia establecida"
DIVERGENCE_LOOKBACK: int = 30    # ventana para buscar los 2 swings de la divergencia
VP_LOOKBACK: int = 100           # velas para construir el Volume Profile
VP_BINS: int = 24
OB_CANDLE_SEARCH: int = 10       # velas hacia atrás para buscar la vela opuesta (Order Block)
OB_LOOKBACK: int = 70            # velas hacia atrás para buscar el swing estructural que rompe el impulso
OB_IMPULSE_ATR_MULT: float = 1.5 # múltiplo de ATR que debe superar el rango de la vela de impulso


# ─────────────────────────────────────────────────────────
# Pesos por estrategia (ensemble)
# ─────────────────────────────────────────────────────────
# Peso de cada estrategia en el cálculo del score del ensemble, en %.
# 100 = peso normal (neutro). Con todos en 100 el comportamiento es
# idéntico a no tener pesos. Se usa tanto en el caso de una sola
# estrategia disparando (score_parcial x peso/100) como en el promedio
# ponderado cuando hay confluencia de 2+ estrategias — ver
# ensemble/ensemble.py para la fórmula completa.
STRATEGY_WEIGHTS: dict[str, int] = {
    "SMC_REVERSAL": 100,
    "BREAKOUT": 100,
    "TREND_PULLBACK": 100,
    "RSI_DIVERGENCE": 100,
    "VP_MEAN_REVERT": 100,
    "LIQUIDITY_GRAB": 100,
    "ORDER_BLOCK": 100,
}


# ─────────────────────────────────────────────────────────
# Ensemble / Score / Probabilidad
# ─────────────────────────────────────────────────────────
MAX_SOLO_SCORE: int = 70             # techo de score cuando dispara UNA sola estrategia (sin confluencia)
MIN_CONFLUENCE_FOR_NORMAL: int = 2   # una señal "normal" (tamaño completo) necesita >=2 estrategias de
                                      # acuerdo; con solo 1 estrategia, la señal SIEMPRE se trata como
                                      # "roja" como mucho
CONFLUENCE_BONUS: int = 5            # puntos extra por cada estrategia adicional en la misma dirección
PROB_AT_SCORE_0: float = 0.30        # probabilidad heurística cuando score=0
PROB_AT_SCORE_100: float = 0.85      # probabilidad heurística cuando score=100
# NOTA: esta "Prob" es una transformación del score, NO una probabilidad
# estadística basada en backtest (no existe ese modelo). Ajusta
# PROB_AT_SCORE_0/100 si más adelante se calibra con resultados reales.


# ─────────────────────────────────────────────────────────
# Umbrales de filtrado
# ─────────────────────────────────────────────────────────
MIN_SCORE: int = 60
MIN_PROB: float = 0.40


# ─────────────────────────────────────────────────────────
# Señales "rojas" (baja confianza, no descartadas del todo)
# ─────────────────────────────────────────────────────────
RED_MIN_PROB: float = 0.40       # por debajo de esto, la señal se descarta directamente
RED_SIZE_FACTOR: float = 0.30    # tamaño de posición reducido para señales rojas
RED_MAX_PER_DAY: int = 2         # máximo de señales rojas ejecutadas por día (global)
RED_TP_CAP_R: float = 1.7        # TP capado a 1.7R en señales rojas


# ─────────────────────────────────────────────────────────
# Threshold dinámico
# ─────────────────────────────────────────────────────────
USE_DYNAMIC_THRESHOLD: bool = True
DYNAMIC_THRESHOLD_LOOKBACK_TRADES: int = 10   # nº de resultados recientes que se recuerdan
DYNAMIC_THRESHOLD_STEP: int = 5               # cuánto sube/baja MIN_SCORE cada vez
DYNAMIC_THRESHOLD_MIN: int = 50
DYNAMIC_THRESHOLD_MAX: int = 75
DYNAMIC_LOSING_STREAK_TO_RAISE: int = 3       # N pérdidas seguidas -> sube el umbral
DYNAMIC_WINNING_STREAK_TO_LOWER: int = 3      # N ganancias seguidas -> baja el umbral


# ─────────────────────────────────────────────────────────
# Gestión de posiciones
# ─────────────────────────────────────────────────────────
MAX_CONCURRENT_TRADES: int = 2   # máximo de posiciones abiertas a la vez (todos los símbolos)
MAX_TRADES_PER_SYMBOL: int = 1   # máximo 1 posición por activo
COOLDOWN_HOURS: int = 4          # horas de espera en un símbolo tras cerrar un trade


# ─────────────────────────────────────────────────────────
# Riesgo / TP
# ─────────────────────────────────────────────────────────
RISK_PRESET: str = "Balanced"
USE_BREAK_EVEN: bool = True

# Presets de riesgo (SL en xATR, TP1/TP2/TP3 en múltiplos-R).
# Antes vivían hardcodeados en strategy_rodri.py; se centralizan aquí
# porque son configuración, no lógica.
RISK_PRESETS: dict[str, dict] = {
    "Conservative": {"sl_mult": 2.5, "tp_mults": [1.0, 2.0, 4.0]},
    "Balanced":     {"sl_mult": 1.5, "tp_mults": [1.0, 2.0, 3.0]},
    "Aggressive":   {"sl_mult": 1.0, "tp_mults": [1.5, 2.5, 4.0]},
    "Scalping":     {"sl_mult": 0.8, "tp_mults": [0.8, 1.5, 2.0]},
}


# ─────────────────────────────────────────────────────────
# Apalancamiento sugerido (según volatilidad ATR%)
# ─────────────────────────────────────────────────────────
LEVERAGE_MIN: int = 5
LEVERAGE_MAX: int = 20
LEV_ATR_PCT_LOW: float = 0.3     # ATR%/precio <= esto -> leverage máximo
LEV_ATR_PCT_HIGH: float = 2.0    # ATR%/precio >= esto -> leverage mínimo


# ─────────────────────────────────────────────────────────
# Gráfico de señal (imagen adjunta al mensaje de apertura)
# ─────────────────────────────────────────────────────────
CHART_LOOKBACK_CANDLES: int = 150   # nº de velas mostradas en el gráfico de cada señal


# ─────────────────────────────────────────────────────────
# Persistencia y ritmo
# ─────────────────────────────────────────────────────────
TRADE_LOG_MAX: int = 300            # nº máximo de operaciones cerradas que se guardan en el historial
STATE_FILE: str = "state_rodri.json"
CHECK_INTERVAL_SECONDS: int = 60    # solo aplica en modo bucle local (sin --once)


# ─────────────────────────────────────────────────────────
# Resumen diario
# ─────────────────────────────────────────────────────────
SEND_DAILY_SUMMARY: bool = True
DAILY_SUMMARY_HOUR_UTC: int = 0


# ─────────────────────────────────────────────────────────
# Etiqueta general de la estrategia
# ─────────────────────────────────────────────────────────
STRATEGY_LABEL: str = "Rodri v1.0 (Multi-Estrategia)"