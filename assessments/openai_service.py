"""
Servicio de integración con OpenAI para generar pruebas técnicas
"""
import json
import os
from openai import OpenAI
from django.conf import settings


class OpenAIAssessmentService:
    """Servicio para generar preguntas técnicas usando OpenAI"""
    
    def __init__(self):
        api_key = getattr(settings, 'OPENAI_API_KEY', os.getenv('OPENAI_API_KEY'))
        if not api_key:
            raise ValueError("OPENAI_API_KEY no está configurada en settings o variables de entorno")
        self.client = OpenAI(api_key=api_key)
        
    def generate_quiz_questions(self, topic, difficulty="MEDIUM", num_questions=10, language="es"):
        """
        Genera preguntas de cuestionario técnico
        
        Args:
            topic: Tema técnico (ej: "Python avanzado", "React Hooks", "Algoritmos")
            difficulty: EASY, MEDIUM, HARD
            num_questions: Cantidad de preguntas a generar
            language: Idioma de las preguntas (es, en)
            
        Returns:
            Lista de diccionarios con preguntas
        """
        difficulty_map = {
            "EASY": "fácil, conceptos básicos",
            "MEDIUM": "intermedio, aplicación práctica",
            "HARD": "avanzado, casos complejos y optimización"
        }
        
        prompt = f"""Genera {num_questions} preguntas de opción múltiple sobre {topic} de nivel {difficulty_map.get(difficulty, 'intermedio')}.

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido, sin texto adicional antes o después.

Formato JSON requerido:
{{
  "questions": [
    {{
      "question_text": "¿Pregunta aquí?",
      "question_type": "MULTIPLE_CHOICE",
      "options": ["Opción A", "Opción B", "Opción C", "Opción D"],
      "correct_answer": "0",
      "explanation": "Explicación detallada de por qué la respuesta es correcta",
      "points": 10
    }}
  ]
}}

Reglas:
- Cada pregunta debe tener exactamente 4 opciones
- correct_answer debe ser el índice (0-3) de la opción correcta
- Las preguntas deben ser técnicas y relevantes para {topic}
- Incluye una explicación clara de la respuesta correcta
- Varía la dificultad dentro del nivel {difficulty_map.get(difficulty)}
- Idioma: {'español' if language == 'es' else 'inglés'}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Eres un experto en crear evaluaciones técnicas de programación. Respondes SOLO con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("questions", [])
            
        except Exception as e:
            raise Exception(f"Error al generar preguntas con OpenAI: {str(e)}")
    
    def generate_coding_challenges(self, topic, difficulty="MEDIUM", num_challenges=3, language="python"):
        """
        Genera desafíos de código práctico
        
        Args:
            topic: Tema técnico
            difficulty: EASY, MEDIUM, HARD
            num_challenges: Cantidad de desafíos
            language: Lenguaje de programación (python, javascript, java, etc.)
            
        Returns:
            Lista de diccionarios con desafíos de código
        """
        difficulty_map = {
            "EASY": "básico, sintaxis fundamental",
            "MEDIUM": "intermedio, estructuras de datos y algoritmos",
            "HARD": "avanzado, optimización y patrones complejos"
        }
        
        prompt = f"""Genera {num_challenges} desafíos de programación en {language} sobre {topic} de nivel {difficulty_map.get(difficulty, 'intermedio')}.

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido.

Formato JSON requerido:
{{
  "challenges": [
    {{
      "question_text": "Descripción del problema a resolver",
      "question_type": "CODE",
      "programming_language": "{language}",
      "code_snippet": "# Plantilla inicial del código\\ndef solution():\\n    pass",
      "test_cases": [
        {{"input": "datos de entrada", "expected_output": "salida esperada", "description": "Caso 1"}},
        {{"input": "otros datos", "expected_output": "otra salida", "description": "Caso 2"}}
      ],
      "explanation": "Explicación de la solución óptima",
      "points": 20
    }}
  ]
}}

Reglas:
- Incluye al menos 3 test cases por desafío
- El code_snippet debe tener una plantilla inicial útil
- Los test cases deben cubrir casos normales, edge cases
- Explicación debe incluir la complejidad temporal y espacial
- Nivel: {difficulty_map.get(difficulty)}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"Eres un experto en crear desafíos de programación en {language}. Respondes SOLO con JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get("challenges", [])
            
        except Exception as e:
            raise Exception(f"Error al generar desafíos con OpenAI: {str(e)}")
    
    def evaluate_code_answer(self, question_text, candidate_code, test_cases, language="python", difficulty="MEDIUM"):
        """
        Evalúa una respuesta de código usando OpenAI
        
        Args:
            question_text: Enunciado de la pregunta
            candidate_code: Código enviado por el candidato
            test_cases: Lista de casos de prueba
            language: Lenguaje de programación
            difficulty: Nivel de dificultad (EASY, MEDIUM, HARD)
            
        Returns:
            Dict con evaluación y feedback
        """
        
        # Mapeo de dificultad a criterios de evaluación
        difficulty_criteria = {
            "EASY": {
                "funcionalidad": 70,
                "correctitud": 15,
                "legibilidad": 10,
                "eficiencia": 5,
                "min_score": 80,  # Si pasa todos los tests
                "description": "nivel BÁSICO/FÁCIL"
            },
            "MEDIUM": {
                "funcionalidad": 60,
                "correctitud": 20,
                "legibilidad": 10,
                "eficiencia": 10,
                "min_score": 75,  # Si pasa todos los tests
                "description": "nivel INTERMEDIO"
            },
            "HARD": {
                "funcionalidad": 50,
                "correctitud": 25,
                "legibilidad": 10,
                "eficiencia": 15,
                "min_score": 70,  # Si pasa todos los tests
                "description": "nivel AVANZADO"
            }
        }
        
        criteria = difficulty_criteria.get(difficulty, difficulty_criteria["MEDIUM"])
        
        prompt = f"""Evalúa el siguiente código del candidato para un ejercicio de {criteria['description']}:

PREGUNTA:
{question_text}

CÓDIGO DEL CANDIDATO ({language}):
```{language}
{candidate_code}
```

CASOS DE PRUEBA:
{json.dumps(test_cases, indent=2)}

🎯 ESCALA DE PUNTAJES QUE DEBES USAR:
- Si el código funciona y pasa TODOS los tests → MÍNIMO {criteria['min_score']}% (hasta 100%)
- Si el código funciona y pasa la mayoría de tests → 60-{criteria['min_score']-1}%
- Si el código funciona parcialmente → 40-59%
- Si el código tiene errores graves → 0-39%

📊 CRITERIOS (usa estos pesos):
1. FUNCIONALIDAD ({criteria['funcionalidad']}%): ¿Funciona? ¿Pasa los tests?
2. CORRECTITUD ({criteria['correctitud']}%): ¿La lógica es correcta?
3. LEGIBILIDAD ({criteria['legibilidad']}%): ¿Es claro?
4. EFICIENCIA ({criteria['eficiencia']}%): ¿Es razonable?

⚠️ REGLAS OBLIGATORIAS:
✅ Si "is_correct": true → el "score_percentage" DEBE ser MÍNIMO {criteria['min_score']}%
✅ Si TODOS los "test_results" tienen "passed": true → MÍNIMO {criteria['min_score']}%
✅ NO seas demasiado estricto con código que funciona correctamente
✅ Este es {criteria['description']}, ajusta expectativas según el nivel

Responde SOLO con JSON:
{{
  "is_correct": true/false,
  "score_percentage": NÚMERO_ENTRE_0_Y_100,
  "feedback": "Análisis del código destacando fortalezas primero",
  "strengths": ["fortaleza 1", "fortaleza 2"],
  "improvements": ["sugerencia 1", "sugerencia 2"],
  "test_results": [
    {{"test_case": 1, "passed": true/false, "message": "resultado del test 1"}},
    {{"test_case": 2, "passed": true/false, "message": "resultado del test 2"}}
  ]
}}

RECORDATORIO FINAL: Si marcas "is_correct": true, el score_percentage NO puede ser menor a {criteria['min_score']}."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": f"Eres un evaluador de código {language}. REGLA CRÍTICA: Si el código funciona correctamente (is_correct=true), el score_percentage DEBE ser MÍNIMO {criteria['min_score']}%. Si todos los tests pasan, MÍNIMO {criteria['min_score']}%. Respondes SOLO JSON válido. Sé JUSTO y GENEROSO con código funcional."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Más determinístico para puntajes consistentes
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # VALIDACIÓN ROBUSTA: Asegurar puntaje mínimo
            score = result.get("score_percentage", 0)
            is_correct = result.get("is_correct", False)
            test_results = result.get("test_results", [])
            
            # Verificar si todos los tests pasaron
            all_tests_passed = False
            if test_results:
                all_tests_passed = all(t.get("passed", False) for t in test_results)
            
            # Si el código es correcto O todos los tests pasaron, aplicar puntaje mínimo
            if (is_correct or all_tests_passed) and score < criteria["min_score"]:
                result["score_percentage"] = criteria["min_score"]
                result["is_correct"] = True
                result["feedback"] = f"✅ Código funcional que resuelve correctamente el problema. {result.get('feedback', '')}"
            
            if result.get("is_correct") and result.get("score_percentage", 0) < criteria["min_score"]:
                result["score_percentage"] = criteria["min_score"]
            
            return result
            
        except Exception as e:
            raise Exception(f"Error al evaluar código con OpenAI: {str(e)}")