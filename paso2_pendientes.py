"""
Paso 8: mostrar solo lo que TIENES QUE HACER, con la hora de México.

Este archivo reutiliza el inicio de sesión de paso1_classroom.py,
así que ambos deben estar en la misma carpeta.
"""

from datetime import datetime, timedelta, timezone

from paso1_classroom import obtener_servicio

# Querétaro está en UTC-6 todo el año (México ya no usa horario de verano).
ZONA = timezone(timedelta(hours=-6))

# Estados en los que la tarea sigue SIN entregar.
ESTADOS_PENDIENTES = {"NEW", "CREATED", "RECLAIMED_BY_STUDENT"}


def fecha_limite(tarea):
    """Regresa la fecha límite en hora local, o None si no tiene."""
    fecha = tarea.get("dueDate")
    if not fecha:
        return None

    hora = tarea.get("dueTime")
    if hora:
        # Classroom guarda la hora en UTC; la convertimos a hora local.
        utc = datetime(
            fecha["year"], fecha["month"], fecha["day"],
            hora.get("hours", 0), hora.get("minutes", 0),
            tzinfo=timezone.utc,
        )
        return utc.astimezone(ZONA)

    # Sin hora: la tomamos como fin del día local.
    return datetime(fecha["year"], fecha["month"], fecha["day"], 23, 59, tzinfo=ZONA)


def obtener_tareas(servicio):
    """Junta las tareas de todos tus cursos activos (con todas las páginas)."""
    resultado = []

    cursos = servicio.courses().list(courseStates=["ACTIVE"]).execute().get("courses", [])

    for curso in cursos:
        token = None
        while True:
            respuesta = (
                servicio.courses()
                .courseWork()
                .list(courseId=curso["id"], pageToken=token)
                .execute()
            )

            for tarea in respuesta.get("courseWork", []):
                entregas = (
                    servicio.courses()
                    .courseWork()
                    .studentSubmissions()
                    .list(courseId=curso["id"], courseWorkId=tarea["id"], userId="me")
                    .execute()
                    .get("studentSubmissions", [])
                )
                estado = entregas[0]["state"] if entregas else "DESCONOCIDO"

                resultado.append(
                    {
                        "curso": curso["name"],
                        "titulo": tarea["title"],
                        "descripcion": tarea.get("description", ""),
                        "limite": fecha_limite(tarea),
                        "estado": estado,
                        "link": tarea.get("alternateLink", ""),
                    }
                )

            # Si hay más páginas, seguimos pidiendo; si no, terminamos.
            token = respuesta.get("nextPageToken")
            if not token:
                break

    return resultado


def mostrar(tareas, titulo):
    print(f"\n=== {titulo} ({len(tareas)}) ===")
    if not tareas:
        print("  (ninguna)")
    for t in tareas:
        if t["limite"]:
            cuando = t["limite"].strftime("%d/%m/%Y %H:%M")
        else:
            cuando = "sin fecha"
        print(f"  - [{t['curso']}] {t['titulo']}")
        print(f"      entrega: {cuando}")


def main():
    servicio = obtener_servicio()
    ahora = datetime.now(ZONA)

    pendientes = [t for t in obtener_tareas(servicio) if t["estado"] in ESTADOS_PENDIENTES]

    proximas = [t for t in pendientes if t["limite"] is None or t["limite"] >= ahora]
    vencidas = [t for t in pendientes if t["limite"] is not None and t["limite"] < ahora]

    # Primero las que vencen antes; las que no tienen fecha, al final.
    proximas.sort(key=lambda t: t["limite"] or datetime.max.replace(tzinfo=ZONA))
    vencidas.sort(key=lambda t: t["limite"])

    mostrar(proximas, "PENDIENTES POR ENTREGAR")
    mostrar(vencidas, "VENCIDAS SIN ENTREGAR")


if __name__ == "__main__":
    main()
