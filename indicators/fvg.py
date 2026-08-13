"""
indicators/fvg.py

Responsabilidad: detectar un Fair Value Gap (FVG) clásico de 3 velas,
usado como confirmación de la estrategia ORDER_BLOCK.

Qué hace:
    - Comprueba si existe un hueco de precio entre la vela 'pos-2' y la
      vela 'pos' (la vela intermedia 'pos-1' no participa en el cálculo,
      solo marca los bordes de la zona): es la definición estándar de FVG
      de 3 velas usada en Smart Money Concepts / ICT.
    - Devuelve la dirección del hueco (ALCISTA/BAJISTA) y sus bordes de
      precio (zone_low, zone_high).

Qué NO hace:
    - No decide si el FVG está contenido dentro de ninguna vela concreta
      (eso lo hace quien lo consuma, ver strategies/order_block.py).
    - No añade columnas al DataFrame: se calcula bajo demanda para una
      posición concreta, igual que indicators/volume_profile.py.

Migrado 1:1 desde indicators_rodri.py (detect_fvg). Trabaja con índices
posicionales (0..n-1).
"""
import pandas as pd


def detect_fvg(df: pd.DataFrame, pos: int):
    """
    Comprueba si existe un Fair Value Gap (FVG) clásico de 3 velas
    terminando en la posición 'pos' (velas pos-2, pos-1, pos):
      - FVG alcista: el low de la vela 'pos' queda por encima del high de
        la vela 'pos-2' -> hueco de precio entre ambas que el mercado no
        llegó a operar.
      - FVG bajista: el high de la vela 'pos' queda por debajo del low de
        la vela 'pos-2'.
    Devuelve {"direction": "ALCISTA"/"BAJISTA", "zone_low": .., "zone_high": ..}
    o None si no hay hueco o no hay velas suficientes.
    """
    if pos < 2 or pos >= len(df):
        return None

    high_a = df.iloc[pos - 2]["high"]
    low_a = df.iloc[pos - 2]["low"]
    high_c = df.iloc[pos]["high"]
    low_c = df.iloc[pos]["low"]

    if pd.isna(high_a) or pd.isna(low_a) or pd.isna(high_c) or pd.isna(low_c):
        return None

    if low_c > high_a:
        return {"direction": "ALCISTA", "zone_low": high_a, "zone_high": low_c}

    if high_c < low_a:
        return {"direction": "BAJISTA", "zone_low": high_c, "zone_high": low_a}

    return None