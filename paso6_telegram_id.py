"""
Paso 19: conseguir tu chat id de Telegram.

Antes de correrlo:
  1. Ten en tu archivo .env una línea:  TELEGRAM_TOKEN=tu_token
  2. Escríbele "hola" a tu bot desde Telegram.

El script lee ese mensaje, saca tu chat id y lo guarda en el .env
(línea TELEGRAM_CHAT_ID=...). Después te manda un mensaje de prueba.
No necesita instalar nada extra.
"""

import json
import os
import urllib.parse
import urllib.request

from dotenv import load_dotenv


def llamar(token, metodo, datos=None):
    """Hace una llamada a la API de Telegram y regresa la respuesta como diccionario."""
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    cuerpo = urllib.parse.urlencode(datos).encode() if datos else None
    with urllib.request.urlopen(urllib.request.Request(url, data=cuerpo), timeout=20) as r:
        return json.loads(r.read().decode())


def guardar_en_env(clave, valor):
    """Agrega o actualiza una línea CLAVE=valor en el archivo .env."""
    lineas = []
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8") as f:
            lineas = f.read().splitlines()
    lineas = [l for l in lineas if not l.startswith(clave + "=")]
    lineas.append(f"{clave}={valor}")
    with open(".env", "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")


def main():
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        print("No encontré TELEGRAM_TOKEN en tu .env. Agrégalo y guarda el archivo.")
        return

    try:
        bot = llamar(token, "getMe")
    except Exception as error:
        print("No pude conectar con Telegram. Revisa que el token esté bien copiado.")
        print("Detalle:", error)
        return
    print(f"Bot encontrado: @{bot['result']['username']}")

    mensajes = llamar(token, "getUpdates")["result"]
    chats = [m["message"]["chat"] for m in mensajes if "message" in m]
    if not chats:
        print("\nEl bot aún no ha recibido mensajes.")
        print("Abre Telegram, entra al chat de tu bot, escríbele 'hola' y vuelve a correr esto.")
        return

    chat_id = chats[-1]["id"]
    guardar_en_env("TELEGRAM_CHAT_ID", chat_id)
    print("Listo: guardé TELEGRAM_CHAT_ID en tu archivo .env")

    llamar(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "🥥 ¡Hola! Ya estoy conectado. Desde ahora te voy a avisar aquí cuando toque empezar tus tareas.",
    })
    print("Te mandé un mensaje de prueba. Revisa tu Telegram.")


if __name__ == "__main__":
    main()
