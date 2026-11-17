"""
Paso 1: conectar a Google Classroom y listar tus tareas.

Antes de correrlo necesitas:
  1. pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
  2. Tener el archivo credentials.json (de Google Cloud) en la misma carpeta.

La primera vez se abre el navegador para que inicies sesión y des permiso.
Después se guarda un token.json y ya no te lo vuelve a pedir.
"""

import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Permisos de SOLO LECTURA: la app puede ver tus tareas, no modificar nada.
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]


def obtener_servicio():
    """Inicia sesión con Google y regresa el cliente de la API de Classroom."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flujo = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flujo.run_local_server(port=0)
        with open("token.json", "w") as archivo:
            archivo.write(creds.to_json())

    return build("classroom", "v1", credentials=creds)


def formatear_fecha(tarea):
    """Convierte la fecha de entrega de Classroom a texto legible."""
    fecha = tarea.get("dueDate")
    if not fecha:
        return "sin fecha de entrega"
    texto = f"{fecha['day']:02d}/{fecha['month']:02d}/{fecha['year']}"
    hora = tarea.get("dueTime")
    if hora:
        # Classroom guarda la hora en UTC
        texto += f" {hora.get('hours', 0):02d}:{hora.get('minutes', 0):02d} UTC"
    return texto


def main():
    servicio = obtener_servicio()

    respuesta = servicio.courses().list(courseStates=["ACTIVE"]).execute()
    cursos = respuesta.get("courses", [])

    if not cursos:
        print("No encontré cursos activos.")
        return

    for curso in cursos:
        print(f"\n=== {curso['name']} ===")

        tareas = (
            servicio.courses()
            .courseWork()
            .list(courseId=curso["id"])
            .execute()
            .get("courseWork", [])
        )

        if not tareas:
            print("  (sin tareas)")
            continue

        for tarea in tareas:
            entregas = (
                servicio.courses()
                .courseWork()
                .studentSubmissions()
                .list(courseId=curso["id"], courseWorkId=tarea["id"], userId="me")
                .execute()
                .get("studentSubmissions", [])
            )
            estado = entregas[0]["state"] if entregas else "DESCONOCIDO"

            print(f"  - {tarea['title']}")
            print(f"      entrega: {formatear_fecha(tarea)}")
            print(f"      estado:  {estado}")


if __name__ == "__main__":
    main()
