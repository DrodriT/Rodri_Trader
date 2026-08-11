# Imagen del bot "Rodri v1.0". Se construye una sola vez (workflow
# build-image.yml) y se reutiliza en cada disparo del cron
# (run-bot.yml) vía `docker pull`, en vez de reinstalar dependencias en
# cada ejecución.
FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias primero (capa cacheada mientras no cambie
# requirements.txt, aunque cambie el código).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código.
COPY . .

CMD ["python3", "main.py", "--once"]
