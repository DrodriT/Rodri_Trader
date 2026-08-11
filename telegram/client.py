"""
telegram/client.py

Responsabilidad: comunicación HTTP de bajo nivel con la API de Telegram.
Es la ÚNICA parte del proyecto que sabe hacer una petición HTTP a
Telegram.

Qué hace:
    - send_telegram: manda un mensaje de texto (Markdown), con reintento
      en texto plano si falla el parseo de Markdown.
    - send_telegram_photo: manda una foto con caption (Markdown), con
      reintento en texto plano y, si también falla, fallback final a
      mandar el caption como mensaje de texto (send_telegram) para no
      perder la alerta.

Qué NO hace:
    - No sabe qué es una "señal", una "posición" ni un "score" — no
      construye NINGÚN texto de negocio. Eso vive en telegram/messages.py.
    - No decide CUÁNDO se manda un mensaje (eso lo decide
      engine/bot_engine.py, a través de telegram/messages.py).

Migrado 1:1 desde bot_rodri.py (send_telegram, send_telegram_photo). Los
nombres de credenciales (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID) se leen de
'cfg', pasado explícito en vez de importar config/settings.py a nivel de
módulo, por consistencia con el resto del proyecto.
"""
import requests


def send_telegram(cfg, message: str) -> None:
    """Manda un mensaje de texto a Telegram (Markdown, con fallback a texto plano)."""
    if "PON_AQUI" in cfg.TELEGRAM_TOKEN or "PON_AQUI" in cfg.TELEGRAM_CHAT_ID:
        print("[AVISO] Configura TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en config/settings.py (.env)")
        print(message)
        return
    url = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={
            "chat_id": cfg.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
        if resp.status_code != 200:
            print(f"[ERROR Telegram] {resp.status_code}: {resp.text}")
            # Red de seguridad: si el fallo es de parseo de Markdown (p.ej.
            # un '_' suelto que no se saneó), reintenta en texto plano para
            # que el mensaje no se pierda del todo.
            resp2 = requests.post(url, data={
                "chat_id": cfg.TELEGRAM_CHAT_ID,
                "text": message,
            }, timeout=10)
            if resp2.status_code != 200:
                print(f"[ERROR Telegram fallback texto plano] {resp2.status_code}: {resp2.text}")
    except Exception as e:
        print(f"[ERROR Telegram] {e}")


def send_telegram_photo(cfg, image_path: str, caption: str = "") -> None:
    """Manda una foto (el gráfico de la señal) con el texto como caption."""
    if "PON_AQUI" in cfg.TELEGRAM_TOKEN or "PON_AQUI" in cfg.TELEGRAM_CHAT_ID:
        print("[AVISO] Configura TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en config/settings.py (.env)")
        print(caption)
        return
    url = f"https://api.telegram.org/bot{cfg.TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(image_path, "rb") as photo:
            resp = requests.post(url, data={
                "chat_id": cfg.TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "Markdown",
            }, files={"photo": photo}, timeout=20)
        if resp.status_code != 200:
            print(f"[ERROR Telegram photo] {resp.status_code}: {resp.text}")
            # Reintenta la foto sin parse_mode (caption en texto plano):
            # si el fallo era por Markdown mal formado, la foto llega igual.
            with open(image_path, "rb") as photo:
                resp2 = requests.post(url, data={
                    "chat_id": cfg.TELEGRAM_CHAT_ID,
                    "caption": caption,
                }, files={"photo": photo}, timeout=20)
            if resp2.status_code != 200:
                print(f"[ERROR Telegram photo fallback] {resp2.status_code}: {resp2.text}")
                # Último recurso: manda el texto solo, sin imagen, para no
                # perder la alerta.
                send_telegram(cfg, caption)
    except Exception as e:
        print(f"[ERROR Telegram photo] {e}")
        send_telegram(cfg, caption)
