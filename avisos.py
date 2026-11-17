"""
Paso 20: avisos por Telegram.

La app (app.py) llama a procesar() después de cada sincronización con Classroom.
Manda tres tipos de avisos, y cada uno se manda UNA sola vez:

  1. Resumen del día: lo que toca hoy, con el primer paso de cada tarea.
  2. "Ya toca empezar": cuando llega el día recomendado para arrancar una tarea.
     Ese día depende de las horas que tarda y de qué tan difícil es: mientras más
     larga o difícil, más días antes te avisa.
  3. Tarea nueva: cuando aparece algo nuevo en tu Classroom (o la agregas a mano).

Lo que ya se avisó queda guardado en tareas.db (tabla "avisos"), así no se repite.
Necesita en tu .env: TELEGRAM_TOKEN y TELEGRAM_CHAT_ID (los deja el paso 19).
"""

import json
import math
import os
import socket
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from dotenv import load_dotenv

from paso5_cronograma import HORAS_POR_DIA, estado_de

# A partir de esta hora (0 a 23) se manda el resumen del día.
# Si tu computadora se prende más tarde, se manda cuando la app arranque.
HORA_RESUMEN = 8

# Días de colchón antes de la entrega según la dificultad (1 a 5).
# Una tarea difícil te avisa mucho antes que una fácil.
COLCHON = {0: 1, 1: 1, 2: 1, 3: 2, 4: 3, 5: 4}

BD = "tareas.db"
PUERTO = 5000  # el mismo puerto que usa app.py


def configurado():
    load_dotenv()
    return bool(os.getenv("TELEGRAM_TOKEN", "").strip() and os.getenv("TELEGRAM_CHAT_ID", "").strip())


def url_app():
    """Dirección de tu app. Si no pones APP_URL en el .env, se detecta la de tu red."""
    load_dotenv()
    fija = os.getenv("APP_URL", "").strip()
    if fija:
        return fija
    if os.getenv("ACCESO_CELULAR", "no").strip().lower() not in ("si", "sí", "1", "yes"):
        return f"http://localhost:{PUERTO}"  # solo esta computadora
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))  # no manda nada; solo averigua cuál es tu IP
        ip = sock.getsockname()[0]
        sock.close()
        return f"http://{ip}:{PUERTO}"
    except Exception:
        return None


def enviar(texto):
    """Manda un mensaje a tu Telegram con un botón para abrir la app. Regresa True si salió bien."""
    load_dotenv()
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    api = f"https://api.telegram.org/bot{token}/sendMessage"
    enlace = url_app()

    def mandar(cuerpo):
        datos = urllib.parse.urlencode(cuerpo).encode()
        urllib.request.urlopen(urllib.request.Request(api, data=datos), timeout=20).read()

    cuerpo = {"chat_id": chat, "text": texto[:3800]}
    try:
        if enlace:
            boton = {"inline_keyboard": [[{"text": "🥥 Abrir mi app", "url": enlace}]]}
            try:
                mandar({**cuerpo, "reply_markup": json.dumps(boton)})
                return True
            except urllib.error.HTTPError as error:
                if error.code != 400:
                    raise
                # Telegram no aceptó el botón (a veces rechaza direcciones de red local):
                # mandamos la dirección como enlace dentro del texto.
                cuerpo["text"] = texto[:3700] + f"\n\n👉 Abrir mi app: {enlace}"
        mandar(cuerpo)
        return True
    except Exception as error:
        print("No pude mandar el aviso por Telegram:", error)
        return False


def clave(item):
    return f"{item['curso']}|{item['titulo']}"


def inicio_recomendado(item):
    """Día en que conviene empezar: entrega menos días de trabajo menos colchón."""
    if not item["limite"]:
        return None
    dias_trabajo = max(1, math.ceil(item["horas"] / HORAS_POR_DIA))
    colchon = COLCHON.get(item["dificultad"], 1)
    return item["limite"].date() - timedelta(days=dias_trabajo + colchon)


def cuando(item, hoy):
    if not item["limite"]:
        return "sin fecha de entrega"
    n = (item["limite"].date() - hoy).days
    if n == 0:
        return "entrega HOY"
    if n == 1:
        return "entrega mañana"
    return f"entrega en {n} días ({item['limite'].strftime('%d/%m')})"


def detalle(item, hoy):
    lineas = [
        f"• [{item['curso']}] {item['titulo']}",
        f"  {cuando(item, hoy)} · ~{item['horas']:g} h · dificultad {item['dificultad']}/5",
    ]
    if item["pasos"]:
        lineas.append(f"  Empieza con: {item['pasos'][0]}")
    return "\n".join(lineas)


def texto_resumen(items, dias, hoy, forzar):
    bloques = dias.get(hoy, [])
    alertas = [
        f"⚠ {estado_de(i)}: {i['titulo']}"
        for i in items
        if i["limite"] and estado_de(i) != "OK"
    ]
    if not bloques and not alertas and not forzar:
        return None

    if bloques:
        total = sum(h for _, h in bloques)
        lineas = [f"☀️ Hoy toca ({total:g} h):", ""]
        for n, (item, horas) in enumerate(bloques, 1):
            lineas.append(f"{n}. [{item['curso']}] {item['titulo']} · {horas:g} h")
            if item["pasos"]:
                lineas.append(f"   Empieza con: {item['pasos'][0]}")
    else:
        lineas = ["☀️ Hoy no tienes trabajo planeado."]

    if alertas:
        lineas += ["", *alertas]
    sin_fecha = [i for i in items if not i["limite"]]
    if sin_fecha:
        lineas += ["", f"📋 {len(sin_fecha)} tarea(s) sin fecha de entrega"]
    return "\n".join(lineas)


def procesar(items, dias, ahora, forzar=False):
    """Decide qué avisos tocan y los manda. forzar=True manda el resumen aunque ya se haya mandado."""
    if not configurado():
        return False

    hoy = ahora.date()
    bd = sqlite3.connect(BD)
    bd.execute("CREATE TABLE IF NOT EXISTS avisos (clave TEXT PRIMARY KEY, enviado TEXT)")
    primera_vez = bd.execute("SELECT COUNT(*) FROM avisos").fetchone()[0] == 0

    def ya(k):
        return bd.execute("SELECT 1 FROM avisos WHERE clave = ?", (k,)).fetchone() is not None

    def marcar(claves):
        for k in claves:
            bd.execute("INSERT OR IGNORE INTO avisos VALUES (?, ?)", (k, ahora.isoformat()))
        bd.commit()

    listos = [i for i in items if i["analizado"]]
    envios = []  # (texto, claves que se marcan si el envío sale bien)

    # 1) Resumen del día
    k_resumen = "resumen|" + hoy.isoformat()
    if forzar or (ahora.hour >= HORA_RESUMEN and not ya(k_resumen)):
        texto = texto_resumen(items, dias, hoy, forzar)
        if texto:
            envios.append((texto, [] if forzar else [k_resumen]))
        elif not forzar:
            marcar([k_resumen])

    # 2) Ya toca empezar
    ya_toca = []
    for item in listos:
        inicio = inicio_recomendado(item)
        if inicio and hoy >= inicio and not ya("empezar|" + clave(item)):
            ya_toca.append(item)
    if ya_toca:
        texto = "⚡ Ya toca empezar:\n\n" + "\n\n".join(detalle(i, hoy) for i in ya_toca)
        envios.append((texto, ["empezar|" + clave(i) for i in ya_toca]))

    # 3) Tareas nuevas (la primera vez solo se anotan, para no mandarte todo de golpe)
    nuevas = [i for i in listos if not ya("nueva|" + clave(i))]
    if nuevas:
        claves_nuevas = ["nueva|" + clave(i) for i in nuevas]
        if primera_vez:
            marcar(claves_nuevas)
        else:
            para_avisar = [i for i in nuevas if i not in ya_toca]
            if para_avisar:
                titulo = "🆕 Tarea nueva:" if len(para_avisar) == 1 else f"🆕 {len(para_avisar)} tareas nuevas:"
                texto = titulo + "\n\n" + "\n\n".join(detalle(i, hoy) for i in para_avisar)
                envios.append((texto, claves_nuevas))
            else:
                marcar(claves_nuevas)

    for texto, claves in envios:
        if enviar(texto):
            marcar(claves)

    bd.close()
    return True
