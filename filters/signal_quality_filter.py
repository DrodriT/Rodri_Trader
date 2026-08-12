"""
filters/signal_quality_filter.py

Responsabilidad: decidir la CALIDAD de una señal del ensemble ('normal',
'roja' o 'descartada'), combinando el filtro macro (15m), los umbrales
de score/prob/confluencia y el límite diario de señales rojas.

Qué hace:
    - is_macro_aligned: compara la tendencia macro (15m) contra la
      dirección de la señal.
    - classify_signal_quality: clasifica una señal ya alineada con la
      macro en 'normal' / 'roja' / 'descartada', según score, prob y
      confluencia.
    - determine_signal_quality: orquesta las tres reglas completas (macro
      -> score/prob/confluencia -> límite diario de rojas) y devuelve la
      calidad final.

Qué NO hace:
    - No hace peticiones al exchange (macro_trend se recibe ya calculado
      — quien llama es responsable de haberlo obtenido, típicamente
      engine/bot_engine.py vía exchange/market_data.py).
    - No lee ni muta 'state' ni ningún otro dato persistido (el conteo de
      señales rojas usadas hoy se recibe ya resuelto como
      'red_signals_used_today', no como el dict de estado completo).
    - No decide niveles de SL/TP ni apalancamiento (eso es
      risk/risk_management.py).

Todas las funciones de este módulo son puras: mismos argumentos, mismo
resultado, sin efectos secundarios — pensado para poder testearse sin
mocks de exchange ni de estado.

Migrado desde engine/bot_engine.py (is_macro_aligned,
classify_signal_quality, y la secuencia de 3 reglas que antes estaba
inline dentro de check_symbol). engine/bot_engine.py conserva
check_higher_timeframe_trend (hace I/O al exchange) y
red_signals_used_today/register_red_signal/_red_tracker (leen/mutan
state), por la misma razón por la que is_in_cooldown/set_cooldown
también se quedaron allí: no son reglas de negocio puras.
"""


def is_macro_aligned(macro_trend: str, signal_direction: str) -> bool:
    """
    NEUTRAL cuenta como alineado (no bloquea). Solo bloquea una tendencia
    macro EXPLÍCITAMENTE contraria a la dirección de la señal.
    """
    return macro_trend == "NEUTRAL" or macro_trend == signal_direction


def classify_signal_quality(signal: dict, dynamic_min_score: int, cfg) -> str:
    """
    Devuelve 'normal', 'roja' o 'descartada' en base a score/prob/
    confluencia ÚNICAMENTE (no considera macro ni límite diario de
    rojas — eso lo resuelve determine_signal_quality).

    Una señal solo puede ser 'normal' (tamaño completo) si además de
    superar el score/prob mínimos, tiene confluencia de varias
    estrategias (MIN_CONFLUENCE_FOR_NORMAL). Con una sola estrategia
    disparando, como mucho se trata como 'roja'.
    """
    has_confluence = signal["confluence"] >= cfg.MIN_CONFLUENCE_FOR_NORMAL
    if has_confluence and signal["score"] >= dynamic_min_score and signal["prob"] >= cfg.MIN_PROB:
        return "normal"
    if signal["prob"] >= cfg.RED_MIN_PROB:
        return "roja"
    return "descartada"


def determine_signal_quality(signal: dict, macro_trend: str, dynamic_min_score: int,
                              red_signals_used_today: int, cfg) -> str:
    """
    Aplica las tres reglas completas, en orden:
      1. Si la señal no está alineada con la tendencia macro (15m) ->
         'descartada' directamente, sin mirar score/prob/confluencia.
         Se aplica por igual a lo que habría sido señal normal o roja.
      2. Si está alineada -> se clasifica por score/prob/confluencia
         (classify_signal_quality).
      3. Si el resultado es 'roja' pero ya se agotó el límite diario de
         señales rojas (cfg.RED_MAX_PER_DAY) -> se degrada a
         'descartada'.
    """
    if not is_macro_aligned(macro_trend, signal["direction"]):
        return "descartada"

    quality = classify_signal_quality(signal, dynamic_min_score, cfg)
    if quality == "roja" and red_signals_used_today >= cfg.RED_MAX_PER_DAY:
        return "descartada"

    return quality