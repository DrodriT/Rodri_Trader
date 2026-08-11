"""
charting/chart_generator.py

Responsabilidad: generar el gráfico de velas (PNG) que se adjunta al
mensaje de apertura de cada señal.

Qué hace:
    - Dibuja las últimas N velas del símbolo (mismo timeframe de escaneo)
      junto con los niveles de la señal — entrada, stop loss y
      TP1/TP2/TP3 — como líneas horizontales.
    - Añade un título con símbolo/dirección/score/prob/estrategia(s).
    - Devuelve la ruta al PNG generado.

Qué NO hace:
    - No manda nada a Telegram (eso lo hace quien llama, vía
      telegram/messages.py, pasándole la ruta del PNG resultante).
    - No calcula ningún indicador ni nivel de riesgo (los recibe ya
      calculados).

Migrado 1:1 desde chart_rodri.py (generate_signal_chart). display_symbol
se importa de telegram/messages.py en vez de duplicarse aquí: en el
original, chart_rodri.py y bot_rodri.py tenían cada uno su propia copia
idéntica de esa función (violación de DRY); ahora hay una sola
implementación y ambos módulos la comparten.
"""
import os
import tempfile

import matplotlib
matplotlib.use("Agg")  # sin display, solo generar PNG
import mplfinance as mpf
import pandas as pd

from telegram.messages import display_symbol


def generate_signal_chart(df: pd.DataFrame, symbol: str, direction: str,
                           score: float, prob: float, strategies: list,
                           entry: float, sl: float, tps: list,
                           lookback_candles: int = 150,
                           out_dir: str = None) -> str:
    """
    Genera un PNG con las últimas 'lookback_candles' velas de 'df' (que
    debe traer ya la columna 'datetime', como la que devuelve
    exchange/market_data.py) más líneas horizontales:
      - SL en rojo
      - Entrada en azul
      - TP1/TP2/TP3 en verde

    tps: lista de precios [tp1, tp2, tp3] en ese orden (o los que haya).
    Devuelve la ruta al PNG generado (queda en un directorio temporal si
    no se indica out_dir).
    """
    plot_df = df.tail(lookback_candles).copy()
    plot_df = plot_df.set_index(pd.DatetimeIndex(plot_df["datetime"]))
    plot_df = plot_df[["open", "high", "low", "close", "volume"]]

    dir_label = "LONG" if direction == "ALCISTA" else "SHORT"
    strat_label = "+".join(strategies)
    title = (f"{display_symbol(symbol)} {dir_label} | Score {score:.0f} | "
             f"Prob {prob:.2f} | {strat_label}")

    levels = [sl, entry] + list(tps)
    colors = ["red", "royalblue"] + ["seagreen"] * len(tps)

    mc = mpf.make_marketcolors(up="tab:green", down="tab:red", inherit=True)
    style = mpf.make_mpf_style(base_mpf_style="nightclouds", marketcolors=mc, gridstyle=":")

    if out_dir is None:
        out_dir = tempfile.gettempdir()
    os.makedirs(out_dir, exist_ok=True)
    ts = int(plot_df.index[-1].timestamp())
    out_path = os.path.join(out_dir, f"chart_{display_symbol(symbol)}_{ts}.png")

    mpf.plot(
        plot_df,
        type="candle",
        style=style,
        hlines=dict(hlines=levels, colors=colors, linestyle="--", linewidths=1.0),
        title=title,
        volume=False,
        figsize=(9, 6),
        savefig=dict(fname=out_path, dpi=110, bbox_inches="tight"),
    )

    return out_path
