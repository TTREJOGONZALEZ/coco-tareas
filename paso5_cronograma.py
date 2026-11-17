"""
Paso 12: armar el cronograma.

Toma tus tareas pendientes (con las horas que estimó la IA) y reparte
el trabajo por días, empezando HOY, respetando cuántas horas puedes
dedicarle a tareas por día. Las tareas que vencen antes se acomodan primero.

Necesita que ya hayas corrido paso4_analizar.py al menos una vez.
Los archivos paso1 a paso4 deben estar en la misma carpeta.
"""

import json
from datetime import datetime, timedelta

from paso1_classroom import obtener_servicio
from paso2_pendientes import ESTADOS_PENDIENTES, ZONA, obtener_tareas
from paso4_analizar import abrir_bd, clave_de

# Cuántas horas al día puedes dedicarle a tareas. Cámbialo cuando quieras.
HORAS_POR_DIA = 2.0

DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def juntar_con_analisis(bd, tareas):
    """Une cada tarea de Classroom con su análisis guardado en la base de datos."""
    con_fecha, sin_fecha, sin_analisis = [], [], []

    for tarea in tareas:
        fila = bd.execute(
            "SELECT horas, dificultad, pasos FROM analisis WHERE clave = ?",
            (clave_de(tarea),),
        ).fetchone()

        if not fila:
            sin_analisis.append(tarea)
            continue

        horas, dificultad, pasos_json = fila
        pasos = json.loads(pasos_json) or [None]
        item = {
            "curso": tarea["curso"],
            "titulo": tarea["titulo"],
            "limite": tarea["limite"],
            "horas": horas or 1.0,
            "dificultad": dificultad,
            "primer_paso": pasos[0],
            "fin": None,  # aquí guardaremos el día en que terminas la tarea
        }
        if tarea["limite"]:
            con_fecha.append(item)
        else:
            sin_fecha.append(item)

    return con_fecha, sin_fecha, sin_analisis


def armar_cronograma(items, hoy):
    """
    Reparte las horas de cada tarea en los días disponibles, empezando hoy.
    Regresa un diccionario: día -> lista de (tarea, horas ese día).
    """
    dias = {}
    ocupado = {}

    # Primero las tareas que vencen antes.
    for item in sorted(items, key=lambda i: i["limite"]):
        restante = item["horas"]
        dia = hoy

        while restante > 0.001 and (dia - hoy).days < 365:
            libre = HORAS_POR_DIA - ocupado.get(dia, 0.0)
            if libre > 0.001:
                bloque = min(libre, restante)
                dias.setdefault(dia, []).append((item, bloque))
                ocupado[dia] = ocupado.get(dia, 0.0) + bloque
                restante -= bloque
                item["fin"] = dia
            dia += timedelta(days=1)

    return dias


def estado_de(item):
    """OK = terminas con al menos un día de colchón; JUSTO = terminas el último día."""
    if item["fin"] is None:
        return "SIN LUGAR"
    limite = item["limite"].date()
    if item["fin"] <= limite - timedelta(days=1):
        return "OK"
    if item["fin"] <= limite:
        return "JUSTO"
    return "NO ALCANZA"


def mostrar(dias, items, sin_fecha, sin_analisis):
    print("\n========== CRONOGRAMA ==========")
    if not dias:
        print("\n  (no hay tareas con fecha de entrega para acomodar)")

    ya_mostrado = set()
    for dia in sorted(dias):
        total = sum(horas for _, horas in dias[dia])
        nombre = DIAS_SEMANA[dia.weekday()].capitalize()
        print(f"\n{nombre} {dia.strftime('%d/%m')}  ({total:g} h)")

        for item, horas in dias[dia]:
            print(f"  - {horas:g} h  [{item['curso']}] {item['titulo']}")
            # El primer paso solo se muestra la primera vez que aparece la tarea.
            if id(item) not in ya_mostrado and item["primer_paso"]:
                print(f"      empieza con: {item['primer_paso']}")
            ya_mostrado.add(id(item))

    print("\n========== AVISOS ==========")
    hay_avisos = False
    for item in items:
        estado = estado_de(item)
        if estado != "OK":
            hay_avisos = True
            termina = item["fin"].strftime("%d/%m") if item["fin"] else "?"
            entrega = item["limite"].strftime("%d/%m")
            print(f"  ! {estado}: {item['titulo']} (terminas el {termina}, entrega el {entrega})")
    if not hay_avisos:
        print("  Todo cabe con holgura.")

    if sin_fecha:
        print(f"\n========== SIN FECHA ({len(sin_fecha)}) ==========")
        print("  No se acomodan en el cronograma porque no tienen fecha de entrega:")
        for item in sin_fecha:
            print(f"  - [{item['curso']}] {item['titulo']} (~{item['horas']:g} h)")

    if sin_analisis:
        print(f"\n  Nota: {len(sin_analisis)} tarea(s) aún no están analizadas.")
        print("  Corre primero: python paso4_analizar.py")


def main():
    servicio = obtener_servicio()
    ahora = datetime.now(ZONA)

    # Solo las que siguen sin entregar y que no están vencidas.
    tareas = [
        t
        for t in obtener_tareas(servicio)
        if t["estado"] in ESTADOS_PENDIENTES
        and (t["limite"] is None or t["limite"] >= ahora)
    ]

    bd = abrir_bd()
    con_fecha, sin_fecha, sin_analisis = juntar_con_analisis(bd, tareas)
    bd.close()

    dias = armar_cronograma(con_fecha, ahora.date())
    mostrar(dias, con_fecha, sin_fecha, sin_analisis)


if __name__ == "__main__":
    main()
