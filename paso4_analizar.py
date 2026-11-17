"""
Paso 11: unir todo.

1. Lee tus tareas pendientes de Classroom (paso1 + paso2).
2. Le pide a la IA que analice cada una (paso3).
3. Guarda los resultados en una base de datos (tareas.db) para no
   volver a gastar IA con tareas que ya analizó.

Los archivos paso1_classroom.py, paso2_pendientes.py y paso3_probar_ia.py
deben estar en la misma carpeta que este.
"""

import json
import os
import sqlite3
import time
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types

from paso1_classroom import obtener_servicio
from paso2_pendientes import ESTADOS_PENDIENTES, ZONA, obtener_tareas
from paso3_probar_ia import INSTRUCCIONES, MODELO

BD = "tareas.db"

# Modelos a probar en orden. Si el primero está saturado o falla,
# se usa el siguiente. (dict.fromkeys quita repetidos sin cambiar el orden.)
MODELOS = list(dict.fromkeys([MODELO, "gemini-2.5-flash", "gemini-3.5-flash"]))


def abrir_bd():
    """Abre (o crea) la base de datos y la tabla donde guardamos los análisis."""
    conexion = sqlite3.connect(BD)
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS analisis (
            clave TEXT PRIMARY KEY,
            curso TEXT,
            titulo TEXT,
            limite TEXT,
            horas REAL,
            dificultad INTEGER,
            pasos TEXT,
            analizado_en TEXT
        )
        """
    )
    return conexion


def clave_de(tarea):
    """Identificador sencillo de una tarea: curso + título."""
    return f"{tarea['curso']}|{tarea['titulo']}"


def analizar_con_ia(cliente, tarea):
    """Pide el análisis a la IA. Reintenta si está saturada. None si no se pudo."""
    mensaje = (
        f"Curso: {tarea['curso']}\n"
        f"Título: {tarea['titulo']}\n"
        f"Descripción: {tarea['descripcion'][:1500] or '(sin descripción)'}"
    )

    for modelo in MODELOS:
        for intento in range(1, 4):
            try:
                respuesta = cliente.models.generate_content(
                    model=modelo,
                    contents=mensaje,
                    config=types.GenerateContentConfig(
                        system_instruction=INSTRUCCIONES,
                        response_mime_type="application/json",
                    ),
                )
                return json.loads(respuesta.text)
            except Exception as error:
                texto = str(error)
                print(f"    intento {intento} con {modelo} falló: {texto[:90]}")
                # Si el modelo no existe, no tiene caso reintentar con él.
                if "404" in texto or "NOT_FOUND" in texto:
                    break
                time.sleep(5 * intento)

    return None


def mostrar_resumen(bd, tareas):
    print("\n========== TUS TAREAS PENDIENTES ==========")
    # Primero las que vencen antes; las que no tienen fecha, al final.
    ordenadas = sorted(
        tareas, key=lambda t: t["limite"] or datetime.max.replace(tzinfo=ZONA)
    )

    for tarea in ordenadas:
        fila = bd.execute(
            "SELECT horas, dificultad, pasos FROM analisis WHERE clave = ?",
            (clave_de(tarea),),
        ).fetchone()

        cuando = (
            tarea["limite"].strftime("%d/%m/%Y %H:%M")
            if tarea["limite"]
            else "sin fecha"
        )
        print(f"\n[{tarea['curso']}] {tarea['titulo']}")
        print(f"  entrega: {cuando}")

        if fila:
            horas, dificultad, pasos_json = fila
            pasos = json.loads(pasos_json)
            print(f"  estimado: {horas} h | dificultad {dificultad}/5")
            if pasos:
                print(f"  primer paso: {pasos[0]}")
        else:
            print("  (sin análisis todavía)")


def main():
    load_dotenv()
    clave_api = os.getenv("GEMINI_API_KEY")
    if not clave_api:
        print("No encontré GEMINI_API_KEY. Revisa tu archivo .env")
        return

    cliente = genai.Client(api_key=clave_api)
    servicio = obtener_servicio()
    ahora = datetime.now(ZONA)

    # Solo las que siguen sin entregar y que no están vencidas.
    tareas = [
        t
        for t in obtener_tareas(servicio)
        if t["estado"] in ESTADOS_PENDIENTES
        and (t["limite"] is None or t["limite"] >= ahora)
    ]
    print(f"Tareas pendientes por entregar: {len(tareas)}")

    bd = abrir_bd()

    for tarea in tareas:
        clave = clave_de(tarea)
        limite_texto = tarea["limite"].isoformat() if tarea["limite"] else None

        ya_analizada = bd.execute(
            "SELECT 1 FROM analisis WHERE clave = ?", (clave,)
        ).fetchone()

        if ya_analizada:
            # No gastamos IA; solo actualizamos la fecha por si el profe la cambió.
            bd.execute(
                "UPDATE analisis SET limite = ? WHERE clave = ?", (limite_texto, clave)
            )
            continue

        print(f"Analizando: {tarea['titulo']}")
        datos = analizar_con_ia(cliente, tarea)

        if datos is None:
            print("  No se pudo analizar ahorita. Se intentará en la próxima corrida.")
            continue

        bd.execute(
            "INSERT INTO analisis VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                clave,
                tarea["curso"],
                tarea["titulo"],
                limite_texto,
                datos.get("horas_estimadas"),
                datos.get("dificultad"),
                json.dumps(datos.get("pasos", []), ensure_ascii=False),
                ahora.isoformat(),
            ),
        )
        bd.commit()

    bd.commit()
    mostrar_resumen(bd, tareas)
    bd.close()


if __name__ == "__main__":
    main()
