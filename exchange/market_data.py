"""
exchange/market_data.py

Responsabilidad: toda la comunicación con el exchange vía ccxt — crear
la instancia del exchange y obtener velas OHLCV como DataFrame.

Qué hace:
    - create_exchange: instancia el exchange de ccxt indicado en config
      (EXCHANGE_ID, MARKET_TYPE), con rate limit habilitado.
    - fetch_ohlcv: pide velas OHLCV a ccxt y las devuelve como DataFrame
      con columnas timestamp/open/high/low/close/volume/datetime.

Qué NO hace:
    - No calcula ningún indicador (eso vive en indicators/).
    - No decide qué símbolo/timeframe/límite pedir (eso lo decide quien
      llama, típicamente engine/bot_engine.py, usando config/settings.py).
    - No maneja reintentos ni lógica de resiliencia ante fallos de red
      (igual que el bot_rodri.py original: un fallo se propaga y lo
      captura quien orquesta el bucle por símbolo).

Migrado 1:1 desde bot_rodri.py (fetch_ohlcv, y la inicialización del
exchange que antes vivía inline en run_once()).
"""
import ccxt
import pandas as pd


def create_exchange(cfg):
    """Crea la instancia de ccxt para el exchange configurado."""
    exchange_class = getattr(ccxt, cfg.EXCHANGE_ID)
    return exchange_class({
        "enableRateLimit": True,
        "options": {"defaultType": cfg.MARKET_TYPE},
    })


def fetch_ohlcv(exchange, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """Obtiene velas OHLCV y las devuelve como DataFrame con columna 'datetime'."""
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df
