"""
Paso 10: probar que la IA (Gemini) funciona.

Le mandamos una tarea de ejemplo y le pedimos que estime cuánto tarda,
qué tan difícil es y en qué pasos pequeños se puede dividir.

Necesitas un archivo .env en esta carpeta con una línea así:
GEMINI_API_KEY=tu_clave_aqui
"""

import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Si algún día este modelo ya no existe o da error, cambia solo este nombre.
# Alternativa: "gemini-2.5-flash"
MODELO = "gemini-3.5-flash"

# Tarea de ejemplo (más adelante aquí irán tus tareas reales de Classroom).
TAREA_EJEMPLO = {
    "curso": "Ética Profesional",
    "titulo": "Donación de cobijas",
    "descripcion": "Participa en la campaña de donación de cobijas y entrega "
    "una evidencia con fotos y un breve reporte de lo que hiciste.",
}

INSTRUCCIONES = """Eres un asistente que ayuda a un estudiante universitario a planear sus tareas.
Analiza la tarea y responde SOLO con un JSON con estas claves:
- "horas_estimadas": número (horas totales de trabajo para un estudiante promedio)
- "dificultad": entero de 1 a 5 (1 = muy fácil, 5 = muy difícil)
- "pasos": lista de 3 a 5 pasos pequeños y concretos, el primero debe ser algo
  que se pueda empezar en menos de 5 minutos
Responde en español."""


def main():
    # Lee el archivo .env y carga la clave en memoria.
    load_dotenv()
    clave = os.getenv("GEMINI_API_KEY")
    if not clave:
        print("No encontré GEMINI_API_KEY. Revisa que exista el archivo .env")
        return

    cliente = genai.Client(api_key=clave)

    mensaje = (
        f"Curso: {TAREA_EJEMPLO['curso']}\n"
        f"Título: {TAREA_EJEMPLO['titulo']}\n"
        f"Descripción: {TAREA_EJEMPLO['descripcion']}"
    )

    print(f"Probando con el modelo {MODELO}...\n")

    try:
        respuesta = cliente.models.generate_content(
            model=MODELO,
            contents=mensaje,
            config=types.GenerateContentConfig(
                system_instruction=INSTRUCCIONES,
                response_mime_type="application/json",
            ),
        )
    except Exception as error:
        print("Hubo un error al llamar a la IA:")
        print(error)
        return

    print("Respuesta cruda de la IA:")
    print(respuesta.text)

    # Convertimos el texto JSON en datos de Python para poder usarlos.
    try:
        datos = json.loads(respuesta.text)
    except json.JSONDecodeError:
        print("\nLa respuesta no vino en formato JSON válido.")
        return

    print("\n--- Resultado ordenado ---")
    print(f"Horas estimadas: {datos.get('horas_estimadas')}")
    print(f"Dificultad (1-5): {datos.get('dificultad')}")
    print("Pasos:")
    for numero, paso in enumerate(datos.get("pasos", []), start=1):
        print(f"  {numero}. {paso}")


if __name__ == "__main__":
    main()
