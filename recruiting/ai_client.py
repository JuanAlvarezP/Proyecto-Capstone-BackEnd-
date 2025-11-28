import json
from openai import OpenAI
from django.conf import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)
MODEL = "gpt-4o-mini"

SCHEMA = {
  "type": "object",
  "properties": {
    "full_name": {"type": "string"},
    "emails": {"type": "array", "items": {"type": "string"}},
    "phones": {"type": "array", "items": {"type": "string"}},
    "skills": {
      "type": "object",
      "properties": {
        "hard": {"type": "array", "items": {"type": "string"}},
        "soft": {"type": "array", "items": {"type": "string"}}
      }
    },
    "education": {"type": "array"},
    "experience": {"type": "array"},
    "links": {"type": "array"},
    "languages": {"type": "array"},
  },
  "required": ["full_name", "emails", "skills"]
}

SYSTEM_MESSAGE = """
Eres un parser ATS experto.
Extrae información de un CV en español o inglés.
Nunca inventes datos. Si no existe, deja arrays vacíos o string vacío.
Responde SOLO en JSON siguiendo el esquema.
"""

def parse_cv_text(cv_text: str):
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": f"Esquema:\n{json.dumps(SCHEMA)}\n\nCV:\n{cv_text[:20000]}"}
    ]

    result = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1
    )

    content = result.choices[0].message.content

    
def analyze_meeting_transcript(transcript: str, hourly_rate: float):
    """
    Lee el transcript de la reunión y devuelve:
    - resumen del proyecto
    - requerimientos funcionales / no funcionales
    - horas estimadas
    - costo estimado
    """
    prompt = f"""
Eres un analista de requisitos y consultor de proyectos de software.

A partir de la siguiente transcripción de una reunión con un cliente,
identifica los requerimientos del sistema y estima el esfuerzo.

Devuélveme UN SOLO JSON con esta estructura EXACTA:

{{
  "project_summary": "Resumen breve en 3-5 líneas en español",
  "functional_requirements": [
    {{
      "id": "FR1",
      "title": "Título corto",
      "description": "Descripción en lenguaje claro",
      "complexity": "baja|media|alta",
      "estimated_hours": 0
    }}
  ],
  "non_functional_requirements": [
    {{
      "id": "NFR1",
      "description": "Requisito no funcional (rendimiento, seguridad, disponibilidad, etc.)"
    }}
  ],
  "assumptions": [
    "Supuesto 1",
    "Supuesto 2"
  ],
  "risks": [
    "Riesgo 1",
    "Riesgo 2"
  ],
  "total_estimated_hours": 0,
  "hourly_rate": %s,
  "estimated_cost": 0
}}

IMPORTANTE:
- Usa solo números para horas y costos (sin símbolos de moneda).
- Todo el texto en español.
- Si algo no está claro en la reunión, indícalo en 'assumptions' o 'risks'.
""" % hourly_rate

    messages = [
        {
            "role": "system",
            "content": "Eres un experto en levantamiento de requerimientos de proyectos de software."
        },
        {
            "role": "user",
            "content": prompt
        },
        {
            "role": "user",
            "content": f"TRANSCRIPCIÓN DE LA REUNIÓN:\n{transcript[:12000]}"
        },
    ]

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = resp.choices[0].message.content
    
    return json.loads(content)
