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

def calculate_candidate_score(candidate_data, project_requirements):
    """
    Nueva función para calificar al candidato con pesos personalizados.
    candidate_data: El JSON extraído del CV.
    project_requirements: Requerimientos del proyecto (skills, descripción).
    """
    
    system_message = """
    Eres un experto en reclutamiento IT. Tu tarea es calificar la compatibilidad de un candidato.
    Debes devolver un JSON con:
    1. 'skills_score': (0-10) Qué tanto coinciden sus hard/soft skills.
    2. 'experience_score': (0-10) Qué tan relevante es su historia laboral para este proyecto.
    3. 'justification': Una breve explicación de por qué tiene esa nota.
    """
    
    prompt = f"""
    REQUERIMIENTOS DEL PROYECTO:
    {project_requirements}

    DATOS DEL CANDIDATO (Extraídos del CV):
    {json.dumps(candidate_data)}

    Calcula las notas basándote en la relevancia real, no solo en palabras clave.
    """

    result = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(result.choices[0].message.content) #

def parse_cv_text(cv_text: str):
    messages = [
      {"role": "system", "content": SYSTEM_MESSAGE},
      {"role": "user", "content": f"Esquema:\n{json.dumps(SCHEMA)}\n\nCV:\n{cv_text[:20000]}"}
    ]
    try:
      result = client.chat.completions.create(
          model=MODEL,
          messages=messages,
          response_format={"type": "json_object"},
          temperature=0.1
      )

      content = result.choices[0].message.content
      return json.loads(content)

    except Exception as e:
        print(f"❌ Error llamando a OpenAI: {e}")
        # Si algo falla, devolvemos un diccionario vacío en lugar de None
        return {}

    
def analyze_meeting_transcript(transcript: str, hourly_rate: float):
    """
    Lee el transcript de la reunión y devuelve el análisis con skills.
    """
    
    prompt = f"""
    Eres un analista de requisitos y arquitecto de software experto.
    
    A partir de la siguiente transcripción de una reunión con un cliente,
    identifica los requerimientos, estima el esfuerzo y SUGIERE EL STACK TECNOLÓGICO.

    Devuélveme UN SOLO JSON con esta estructura EXACTA:

    {{
      "project_summary": "Resumen breve en 3-5 líneas en español",
      "required_skills": ["Tecnología1", "Tecnología2"], 
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
          "description": "Requisito no funcional"
        }}
      ],
      "project_title": "Nombre sugerido para el proyecto",
      "assumptions": ["Supuesto 1"],
      "risks": ["Riesgo 1"],
      "total_estimated_hours": 0,
      "hourly_rate": {hourly_rate},
      "estimated_cost": 0
    }}

    IMPORTANTE:
    1. Usa solo números para horas y costos.
    2. En "required_skills", devuelve una lista de strings con las tecnologías inferidas o mencionadas (ej: ["React", "Django", "PostgreSQL", "AWS"]). Si no mencionan ninguna, infiere las más adecuadas para el tipo de proyecto.
    """

    messages = [
        {
            "role": "system",
            "content": "Eres un experto en arquitectura de software y análisis de requisitos."
        },
        {
            "role": "user",
            "content": prompt
        },
        {
            "role": "user",
            "content": f"TRANSCRIPCIÓN:\n{transcript[:12000]}"
        },
    ]

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = resp.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        print(f"Error llamando a OpenAI: {e}")
        # Retorno de emergencia para no romper el backend
        return {
            "project_summary": "Error al procesar la reunión.",
            "required_skills": ["Análisis Manual"],
            "estimated_hours": 0,
            "estimated_cost": 0,
            "functional_requirements": []
        }
    

