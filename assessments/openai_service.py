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
        
    def generate_quiz_questions(self, topic, difficulty="MEDIUM", num_questions=10, language="es", include_code_snippets=False):
        """
        Genera preguntas de cuestionario técnico
        
        Args:
            topic: Tema técnico (ej: "Python avanzado", "React Hooks", "Algoritmos")
            difficulty: EASY, MEDIUM, HARD
            num_questions: Cantidad de preguntas a generar
            language: Idioma de las preguntas (es, en)
            include_code_snippets: Si True, genera preguntas con fragmentos de código
            
        Returns:
            Lista de diccionarios con preguntas
        """
        difficulty_map = {
            "EASY": {
                "description": "nivel BÁSICO/JUNIOR",
                "details": "Conceptos fundamentales, sintaxis básica, definiciones estándar",
                "min_time_per_question": 2,  # minutos
                "max_time_per_question": 3
            },
            "MEDIUM": {
                "description": "nivel INTERMEDIO/MID-LEVEL",
                "details": "Aplicación práctica, análisis de código, resolución de problemas reales, comparación de enfoques, debugging",
                "min_time_per_question": 3,
                "max_time_per_question": 5
            },
            "HARD": {
                "description": "nivel AVANZADO/SENIOR",
                "details": "Optimización, arquitectura, patrones de diseño, casos edge complejos, análisis de complejidad, trade-offs",
                "min_time_per_question": 5,
                "max_time_per_question": 7
            }
        }
        
        diff_info = difficulty_map.get(difficulty, difficulty_map["MEDIUM"])
        suggested_time = (diff_info["min_time_per_question"] + diff_info["max_time_per_question"]) / 2 * num_questions
        
        # Instrucciones adicionales para code_snippets
        code_instructions = ""
        code_example = ""
        if include_code_snippets:
            code_instructions = f"""

🔥 GENERACIÓN DE FRAGMENTOS DE CÓDIGO (IMPORTANTE):
- Se requiere que TODAS o la MAYORÍA de las preguntas incluyan fragmentos de código
- Para cada pregunta que requiera código, DEBES incluir AMBOS campos:
  * "question_text": La pregunta que hace referencia al código
  * "code_snippet": El fragmento de código completo y funcional
- El code_snippet debe ser código REAL, ejecutable y relevante para {topic}
- La pregunta puede preguntar sobre: salida, comportamiento, errores, optimización, etc.
- El código debe ser claro, bien formateado y sin errores de sintaxis
- MÍNIMO {int(num_questions * 0.6)} preguntas deben incluir code_snippet"""
            
            code_example = f"""
EJEMPLO DE PREGUNTA CON CÓDIGO:
{{
  "question_text": "¿Cuál es la salida del siguiente código?",
  "code_snippet": "def suma(a, b):\\n    return a + b\\n\\nresultado = suma(3, 5)\\nprint(resultado)",
  "question_type": "MULTIPLE_CHOICE",
  "options": ["3", "5", "8", "Error"],
  "correct_answer": "2",
  "explanation": "La función suma recibe 3 y 5 como parámetros, los suma (3+5=8) y retorna 8. Luego print(8) muestra '8' en la salida.",
  "points": 10
}}"""
        
        prompt = f"""Genera EXACTAMENTE {num_questions} preguntas de opción múltiple sobre {topic} de {diff_info['description']}.

🎯 OBJETIVO: Crear {num_questions} preguntas de ALTA CALIDAD que evalúen comprensión real del tema.{code_instructions}

⏱️ TIEMPO SUGERIDO PARA ESTA EVALUACIÓN: {int(suggested_time)} minutos
   (Aproximadamente {diff_info['min_time_per_question']}-{diff_info['max_time_per_question']} minutos por pregunta para {diff_info['description']})

🔴 CRITERIOS DE CALIDAD PARA {diff_info['description'].upper()}:

1. **Relevancia técnica**: {diff_info['details']}
2. **Profundidad adecuada**: Las preguntas deben requerir {diff_info['min_time_per_question']}-{diff_info['max_time_per_question']} minutos de análisis
3. **Opciones desafiantes**: Los distractores deben ser plausibles pero incorrectos
4. **Variedad**: Incluye diferentes aspectos de {topic}

📋 TIPOS DE PREGUNTAS A INCLUIR (distribuir entre las {num_questions}):
- 30-40%: Conceptos teóricos aplicados
- 30-40%: Análisis de código/escenarios
- 20-30%: Mejores prácticas y comparaciones
- 10-20%: Casos edge y debugging

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido, sin texto adicional antes o después.

Formato JSON requerido:
{{
  "questions": [
    {{
      "question_text": "Pregunta detallada que requiera análisis (mínimo 50 caracteres)",
      "code_snippet": "# Código relevante (OPCIONAL, pero REQUERIDO si include_code_snippets=true)\\ndef ejemplo():\\n    return 42",
      "question_type": "MULTIPLE_CHOICE",
      "options": ["Opción A detallada", "Opción B detallada", "Opción C detallada", "Opción D detallada"],
      "correct_answer": "0",
      "explanation": "Explicación completa de por qué es correcta Y por qué las otras son incorrectas (mínimo 100 caracteres)",
      "points": 10
    }}
  ],
  "suggested_time_minutes": {int(suggested_time)},
  "difficulty_level": "{difficulty}",
  "topic": "{topic}"
}}{code_example}

🚫 EVITA (ERRORES COMUNES):
- ❌ Preguntas que se responden con "sí/no" obvios
- ❌ Definiciones memorizables sin contexto
- ❌ Opciones claramente incorrectas o ridículas
- ❌ Preguntas demasiado simples para {diff_info['description']}
- ❌ Explicaciones vagas o incompletas
✅ BUSCA (BUENAS PRÁCTICAS):
- ✅ Preguntas que requieran razonamiento
- ✅ Escenarios realistas del mundo real
- ✅ Opciones que distingan conocimiento superficial vs profundo
- ✅ Explicaciones que enseñen conceptos adicionales
- ✅ Preguntas que evalúen comprensión, no memorización

REGLAS OBLIGATORIAS:
- Cada pregunta debe tener EXACTAMENTE 4 opciones
- correct_answer debe ser el índice (0-3) de la opción correcta
- question_text debe tener MÍNIMO 50 caracteres
- explanation debe tener MÍNIMO 100 caracteres y explicar por qué las otras opciones son incorrectas
- Todas las opciones deben ser gramaticalmente completas y profesionales
- Varía la posición de la respuesta correcta (no siempre en índice 0)
- Idioma: {'español' if language == 'es' else 'inglés'}

📊 DISTRIBUCIÓN DE COMPLEJIDAD DENTRO DE {diff_info['description']}:
- 20% más fáciles (entrada al nivel)
- 60% complejidad estándar del nivel
- 20% más desafiantes (techo del nivel)

EJEMPLO DE PREGUNTA DE CALIDAD PARA {diff_info['description']}:
{{
  "question_text": "En una aplicación React, tienes un componente que renderiza una lista de 10,000 elementos y notas problemas de rendimiento. ¿Cuál estrategia de optimización sería MÁS efectiva?",
  "question_type": "MULTIPLE_CHOICE",
  "options": [
    "Usar React.memo() en el componente de lista completo",
    "Implementar virtualización con react-window para renderizar solo elementos visibles",
    "Agregar key props a cada elemento de la lista",
    "Usar useCallback en todos los event handlers"
  ],
  "correct_answer": "1",
  "explanation": "La virtualización (opción B) es la más efectiva porque renderiza solo los elementos visibles en el viewport, reduciendo drásticamente el DOM. React.memo ayuda pero no resuelve el problema de 10,000 elementos montados. Las keys son necesarias pero no mejoran el rendimiento significativamente. useCallback optimiza re-renders pero no reduce la cantidad de elementos.",
  "points": 10
}}

Ahora genera EXACTAMENTE {num_questions} preguntas de {diff_info['description']} sobre {topic}:
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": f"Eres un experto senior en crear evaluaciones técnicas de programación de {diff_info['description']}. DEBES generar EXACTAMENTE {num_questions} preguntas. Respondes SOLO con JSON válido. Tus preguntas son desafiantes, relevantes y bien fundamentadas."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,  # Aumentado para más creatividad y variedad
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            questions = result.get("questions", [])
            
            # Validación: asegurar que se generaron suficientes preguntas
            if len(questions) < num_questions:
                print(f"⚠️ ADVERTENCIA: Se generaron solo {len(questions)} de {num_questions} preguntas solicitadas")
            
            # Añadir metadata de tiempo sugerido a cada pregunta
            for question in questions:
                if "suggested_time_minutes" not in question:
                    question["suggested_time_minutes"] = (diff_info["min_time_per_question"] + diff_info["max_time_per_question"]) / 2
            
            return questions
            
        except Exception as e:
            raise Exception(f"Error al generar preguntas con OpenAI: {str(e)}")
    
    def generate_coding_challenges(self, topic, difficulty="MEDIUM", num_challenges=1, language="python"):
        """
        Genera desafíos de código práctico con test_cases automáticos para sandbox
        
        Args:
            topic: Tema técnico
            difficulty: EASY, MEDIUM, HARD
            num_challenges: Cantidad de desafíos (por defecto 1)
            language: Lenguaje de programación (python, javascript, java, etc.)
            
        Returns:
            Lista de diccionarios con desafíos de código y test_cases
        """
        difficulty_map = {
            "EASY": "básico, sintaxis fundamental",
            "MEDIUM": "intermedio, estructuras de datos y algoritmos",
            "HARD": "avanzado, optimización y patrones complejos"
        }
        
        # Ejemplos de sintaxis según lenguaje
        language_examples = {
            "python": {
                "snippet": "def solution(param):\\n    # Tu código aquí\\n    pass",
                "input_example": '"[1, 2, 3]"',
                "output_example": '"6"',
                "note": "Test_cases para Python sandbox - formato JSON estándar",
                "example_one_param": '{"input": "[1, 2, 3]", "expected_output": "6"}',
                "example_multi_param": '{"input": "[[1, 2, 3], 5]", "expected_output": "[1, 2, 3, 5]"}'
            },
            "javascript": {
                "snippet": "function solution(param) {\\n  // Tu código aquí\\n}",
                "input_example": '"[1, 2, 3]"',
                "output_example": '"6"',
                "note": "Test_cases para JavaScript sandbox - formato JSON estándar",
                "example_one_param": '{"input": "[1, 2, 3]", "expected_output": "6"}',
                "example_multi_param": '{"input": "[[1, 2, 3], 5]", "expected_output": "[1, 2, 3, 5]"}'
            },
            "java": {
                "snippet": "public class Solution {\\n  public static int solution(int[] param) {\\n    // Tu código aquí\\n    return 0;\\n  }\\n}",
                "input_example": '"[1, 2, 3]"',
                "output_example": '"6"',
                "note": "Test_cases para Java sandbox - formato JSON estándar",
                "example_one_param": '{"input": "[1, 2, 3]", "expected_output": "6"}',
                "example_multi_param": '{"input": "[[1, 2, 3], 5]", "expected_output": "[1, 2, 3, 5]"}'
            }
        }
        
        lang_info = language_examples.get(language.lower(), language_examples["python"])
        
        prompt = f"""Genera {num_challenges} desafíos de programación en {language} sobre {topic} de nivel {difficulty_map.get(difficulty, 'intermedio')}.

🎯 OBJETIVO: Crear desafíos educativos con test_cases que se ejecutarán en un SANDBOX REAL.

IMPORTANTE: Responde ÚNICAMENTE con un JSON válido, sin texto adicional.

Formato JSON requerido:
{{
  "challenges": [
    {{
      "question_text": "Descripción clara del problema a resolver",
      "question_type": "CODE",
      "programming_language": "{language}",
      "code_snippet": "{lang_info['snippet']}",
      "test_cases": [
        {{
          "description": "Descripción del caso de prueba",
          "input": "STRING JSON con los parámetros",
          "expected_output": "STRING JSON con el resultado esperado"
        }}
      ],
      "explanation": "Explicación de la solución óptima",
      "points": 20
    }}
  ]
}}

🔴 REGLAS CRÍTICAS PARA TEST_CASES (muy importante):

1. **Cantidad**: Genera MÍNIMO 4 test_cases, IDEAL 5-6 test_cases por desafío

2. **Cobertura**: Los test_cases DEBEN cubrir:
   - ✅ Caso básico/feliz (entrada típica)
   - ✅ Caso edge (array vacío, string vacío, null, 0, etc.)
   - ✅ Caso con múltiples elementos
   - ✅ Caso límite (números grandes, strings largos)
   - ✅ Caso especial del dominio del problema

3. **Formato de input y expected_output** (MUY IMPORTANTE):
   - AMBOS deben ser STRINGS JSON válidos
   - Para UN parámetro:
     * Número: "42" o "3.14"
     * String: "\\"texto\\"" (con escapes)
     * Array: "[1, 2, 3]"
     * Boolean: "true" o "false"
     * Null: "null"
   - Para MÚLTIPLES parámetros: usar un ARRAY que contenga todos los parámetros:
     * Dos números: "[5, 10]"
     * Array y número: "[[1, 2, 3, 4, 5], 6]"
     * String y número: "[\\"hello\\", 3]"
     * Tres parámetros: "[param1, param2, param3]"
   
   ⚠️ REGLA CRÍTICA: Si la función recibe múltiples parámetros, el input DEBE ser un array: "[param1, param2]"
   ❌ INCORRECTO: "[1, 2, 3], 6" (esto NO es JSON válido)
   ✅ CORRECTO: "[[1, 2, 3], 6]" (array con dos elementos)

4. **Nota para {language}**: {lang_info['note']}

5. **code_snippet**: Debe ser una plantilla inicial útil pero sin resolver el problema

6. **Problemas realistas**: Crea desafíos educativos, prácticos y relevantes para {topic}

EJEMPLO CORRECTO ({language.upper()} - UN PARÁMETRO):
{{
  "challenges": [
    {{
      "question_text": "Crea una función que sume todos los números pares de un array",
      "question_type": "CODE",
      "programming_language": "{language}",
      "code_snippet": "{lang_info['snippet']}",
      "test_cases": [
        {{
          "description": "Array con números mixtos",
          "input": "[1, 2, 3, 4, 5, 6]",
          "expected_output": "12"
        }},
        {{
          "description": "Array vacío",
          "input": "[]",
          "expected_output": "0"
        }},
        {{
          "description": "Solo números impares",
          "input": "[1, 3, 5, 7]",
          "expected_output": "0"
        }},
        {{
          "description": "Solo números pares",
          "input": "[2, 4, 6, 8]",
          "expected_output": "20"
        }},
        {{
          "description": "Array con un solo elemento par",
          "input": "[10]",
          "expected_output": "10"
        }},
        {{
          "description": "Array con números negativos",
          "input": "[-4, -2, 1, 3]",
          "expected_output": "-6"
        }}
      ],
      "explanation": "La solución óptima usa filter() para números pares y reduce() para sumar. Complejidad O(n) temporal, O(1) espacial.",
      "points": 20
    }}
  ]
}}

EJEMPLO CORRECTO ({language.upper()} - DOS PARÁMETROS):
{{
  "challenges": [
    {{
      "question_text": "Crea una función que filtre números pares de un array y retorne solo los primeros N elementos",
      "question_type": "CODE",
      "programming_language": "{language}",
      "code_snippet": "{lang_info['snippet']}",
      "test_cases": [
        {{
          "description": "Array con números mixtos y límite 2",
          "input": "[[1, 2, 3, 4, 5, 6], 2]",
          "expected_output": "[2, 4]"
        }},
        {{
          "description": "Array vacío",
          "input": "[[], 3]",
          "expected_output": "[]"
        }},
        {{
          "description": "Límite mayor que pares disponibles",
          "input": "[[2, 4, 6], 10]",
          "expected_output": "[2, 4, 6]"
        }},
        {{
          "description": "Solo impares con límite",
          "input": "[[1, 3, 5], 2]",
          "expected_output": "[]"
        }}
      ],
      "explanation": "Filtrar los pares y luego usar slice(0, limite). Complejidad O(n).",
      "points": 20
    }}
  ]
}}

⚠️ VERIFICACIÓN FINAL:
- Cada test_case tiene "description", "input" (string JSON), "expected_output" (string JSON)
- Los valores de input y expected_output están entre comillas y son strings JSON válidos
- Hay al menos 4-6 test_cases por desafío
- Los test_cases cubren casos normales, edge cases y casos límite
- El nivel de dificultad es {difficulty_map.get(difficulty)}
- Los test_cases son COMPATIBLES con sandbox de {language} (Piston API, e0.gg, etc.)
- El formato de input/output es UNIVERSAL y funciona en cualquier sandbox

IMPORTANTE: Los test_cases generados deben ser ejecutables en sandboxes reales para {language}.
El formato JSON debe ser compatible con APIs de ejecución de código como Piston API.

Ahora genera los {num_challenges} desafíos sobre {topic} en {language}:
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
            
            # ⚡⚡⚡ VALIDACIÓN ULTRA ROBUSTA: MÚLTIPLES CAPAS DE VERIFICACIÓN ⚡⚡⚡
            score = result.get("score_percentage", 0)
            is_correct = result.get("is_correct", False)
            test_results = result.get("test_results", [])
            
            # Contar tests que pasaron
            passed_count = 0
            total_count = len(test_results) if test_results else 0
            if test_results:
                passed_count = sum(1 for t in test_results if t.get("passed", False))
            
            all_tests_passed = (total_count > 0 and passed_count == total_count)
            
            # 🔴 CAPA 1: Si is_correct es true, FORZAR puntaje mínimo
            if is_correct:
                if score < criteria["min_score"]:
                    result["score_percentage"] = criteria["min_score"]
                    result["feedback"] = f"✅ Código correcto que resuelve el problema. {result.get('feedback', '')}"
            
            # 🔴 CAPA 2: Si todos los tests pasaron, FORZAR puntaje mínimo
            if all_tests_passed:
                if score < criteria["min_score"]:
                    result["score_percentage"] = criteria["min_score"]
                    result["is_correct"] = True
                    result["feedback"] = f"✅ TODOS los tests pasaron ({passed_count}/{total_count}). {result.get('feedback', '')}"
            
            # 🔴 CAPA 3: Si pasa más del 80% de tests, dar al menos 70%
            if total_count > 0:
                pass_rate = (passed_count / total_count) * 100
                if pass_rate >= 80 and score < 70:
                    result["score_percentage"] = max(70, score)
                    result["is_correct"] = pass_rate == 100
            
            # 🔴 CAPA 4: Verificación final cruzada
            final_score = result.get("score_percentage", 0)
            final_is_correct = result.get("is_correct", False)
            
            if final_is_correct and final_score < criteria["min_score"]:
                result["score_percentage"] = criteria["min_score"]
            
            if all_tests_passed and final_score < criteria["min_score"]:
                result["score_percentage"] = criteria["min_score"]
                result["is_correct"] = True
            
            # 🔴 CAPA 5: Garantía absoluta - última verificación
            ultimate_score = result.get("score_percentage", 0)
            if all_tests_passed and ultimate_score < criteria["min_score"]:
                # Si TODOS los tests pasaron, NO PUEDE ser menos del mínimo
                result["score_percentage"] = criteria["min_score"]
                result["is_correct"] = True
                print(f"⚠️ CORRECCIÓN FORZADA: Score original {score}% -> {criteria['min_score']}% (todos los tests pasaron)")
            
            return result
            
        except Exception as e:
            raise Exception(f"Error al evaluar código con OpenAI: {str(e)}")
    
    def analyze_application_for_assessment(self, application_id):
        """
        Analiza una aplicación (candidato + proyecto) y sugiere parámetros para crear una evaluación
        
        Args:
            application_id: ID de la Application a analizar
            
        Returns:
            Dict con sugerencias para crear evaluación técnica
        """
        from recruiting.models import Application
        from projects.models import Project
        from django.contrib.auth.models import User
        import datetime
        
        try:
            # 1. Obtener la aplicación
            application = Application.objects.select_related('candidate', 'project').get(id=application_id)
            project = application.project
            candidate = application.candidate
            
            # 2. Extraer información relevante
            required_skills = project.required_skills if hasattr(project, 'required_skills') else []
            extracted_data = application.extracted if application.extracted else {}
            candidate_skills = extracted_data.get('skills', [])
            experience_years = extracted_data.get('experience_years', 0)
            
            # Obtener texto del CV (primeros 500 caracteres)
            cv_preview = ""
            if application.parsed_text:
                cv_preview = application.parsed_text[:500]
            
            # 3. Construir prompt para OpenAI
            prompt = f"""Eres un experto en recursos humanos técnicos. Analiza la siguiente información y sugiere parámetros óptimos para una evaluación técnica.

PROYECTO:
- Título: {project.title}
- Descripción: {project.description[:200] if project.description else 'No disponible'}
- Skills requeridos: {', '.join(required_skills) if required_skills else 'No especificados'}
- Prioridad: {project.priority if hasattr(project, 'priority') else 'Media'}

CANDIDATO:
- Username: {candidate.username}
- Años de experiencia detectados: {experience_years}
- Skills del CV: {', '.join(candidate_skills) if candidate_skills else 'No detectados'}
- Match score con proyecto: {application.match_score}%
- Resumen CV: {cv_preview if cv_preview else 'No disponible'}

CONTEXTO ADICIONAL:
- Estado aplicación: {application.status}
- Fecha aplicación: {application.created_at.strftime('%Y-%m-%d') if application.created_at else 'N/A'}

INSTRUCCIONES:
Basándote en el análisis anterior, sugiere:
1. **Título descriptivo** para la evaluación (máx 100 caracteres)
2. **Descripción breve** explicando enfoque (máx 200 caracteres)
3. **Tipo de evaluación**: "QUIZ" (preguntas teóricas) o "CODING" (prueba de código)
4. **Dificultad**: "EASY" (junior/básico), "MEDIUM" (mid-level/intermedio), "HARD" (senior/avanzado)
5. **Tiempo en minutos**: entre 30-120 según complejidad
6. **Score mínimo para aprobar**: entre 60-85%
7. **Número de preguntas**: 5-15 (menos para CODING, más para QUIZ)
8. **Lenguaje de programación** principal (si tipo es CODING)
9. **Nivel de experiencia del candidato**: "junior", "intermediate", "senior"
10. **Complejidad del proyecto**: "low", "medium", "high"
11. **Skills detectados** más relevantes para esta evaluación

CRITERIOS DE DECISIÓN:
- Si match_score >= 80% → EASY (candidato califica bien)
- Si match_score 60-79% → MEDIUM (candidato promedio)
- Si match_score < 60% → HARD (evaluar más a fondo)
- Si required_skills incluye lenguajes de programación → CODING
- Si required_skills son principalmente soft skills o teóricos → QUIZ
- Ajustar tiempo según dificultad y cantidad de preguntas:
  * QUIZ EASY: 2-3 min/pregunta → 8-12 preguntas = 30-45 min
  * QUIZ MEDIUM: 3-5 min/pregunta → 10-15 preguntas = 45-75 min
  * QUIZ HARD: 5-7 min/pregunta → 12-20 preguntas = 60-120 min
  * CODING EASY: 1-2 desafíos = 30-45 min
  * CODING MEDIUM: 2-3 desafíos = 60-90 min
  * CODING HARD: 3-5 desafíos = 90-120 min
- Score mínimo: EASY=65%, MEDIUM=70%, HARD=75%
- Para QUIZ: MÍNIMO 8 preguntas, IDEAL 10-15 preguntas
- Para CODING: 1-5 desafíos según dificultad

RESPONDE EN JSON con esta estructura EXACTA:
{{
  "suggested_title": "...",
  "suggested_description": "...",
  "suggested_type": "QUIZ",
  "suggested_difficulty": "MEDIUM",
  "suggested_time_minutes": 60,
  "suggested_passing_score": 70,
  "suggested_num_questions": 10,
  "suggested_programming_language": "JavaScript",
  "difficulty_reason": "Explicación de por qué esta dificultad es apropiada",
  "time_reason": "Explicación de por qué este tiempo es adecuado",
  "score_reason": "Explicación del score mínimo sugerido",
  "type_reason": "Explicación de por qué QUIZ o CODING",
  "detected_skills": ["skill1", "skill2", "skill3"],
  "candidate_experience_level": "intermediate",
  "project_complexity": "medium"
}}"""

            # 4. Llamar a OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "Eres un experto en recursos humanos técnicos especializado en crear evaluaciones. Respondes ÚNICAMENTE con JSON válido."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validar y normalizar resultado
            result['application_id'] = application_id
            result['analyzed_at'] = datetime.datetime.now().isoformat()
            
            return result
            
        except Application.DoesNotExist:
            raise ValueError(f"Application {application_id} no encontrada")
        except Exception as e:
            # Si OpenAI falla, usar lógica de fallback
            print(f"⚠️ OpenAI falló, usando fallback: {str(e)}")
            return self._get_fallback_suggestions(application_id)
    
    def _get_fallback_suggestions(self, application_id):
        """
        Lógica de fallback si OpenAI no está disponible
        Usa reglas heurísticas para generar sugerencias
        """
        from recruiting.models import Application
        import datetime
        
        try:
            application = Application.objects.select_related('candidate', 'project').get(id=application_id)
            project = application.project
            
            # Determinar dificultad basada en match_score
            if application.match_score >= 80:
                difficulty = "EASY"
                passing_score = 65
                time_minutes = 40
                num_questions_quiz = 10
                num_questions_coding = 2
            elif application.match_score >= 60:
                difficulty = "MEDIUM"
                passing_score = 70
                time_minutes = 60
                num_questions_quiz = 12
                num_questions_coding = 3
            else:
                difficulty = "HARD"
                passing_score = 75
                time_minutes = 90
                num_questions_quiz = 15
                num_questions_coding = 4
            
            # Determinar tipo basado en skills requeridos
            required_skills = project.required_skills if hasattr(project, 'required_skills') else []
            coding_keywords = ['react', 'python', 'java', 'javascript', 'node', 'django', 'angular', 
                             'vue', 'php', 'ruby', 'go', 'rust', 'c++', 'c#', 'swift', 'kotlin']
            has_coding = any(
                any(keyword in str(skill).lower() for keyword in coding_keywords)
                for skill in required_skills
            )
            
            assessment_type = "CODING" if has_coding else "QUIZ"
            num_questions = num_questions_coding if assessment_type == "CODING" else num_questions_quiz
            
            # Detectar lenguaje principal
            programming_language = "JavaScript"
            for skill in required_skills:
                skill_lower = str(skill).lower()
                if 'python' in skill_lower or 'django' in skill_lower:
                    programming_language = "Python"
                    break
                elif 'java' in skill_lower and 'javascript' not in skill_lower:
                    programming_language = "Java"
                    break
                elif 'react' in skill_lower or 'node' in skill_lower or 'javascript' in skill_lower:
                    programming_language = "JavaScript"
                    break
            
            # Determinar nivel de experiencia
            extracted = application.extracted if application.extracted else {}
            experience_years = extracted.get('experience_years', 0)
            if experience_years < 2:
                candidate_experience = "junior"
            elif experience_years < 5:
                candidate_experience = "intermediate"
            else:
                candidate_experience = "senior"
            
            # Complejidad del proyecto
            if project.priority <= 2:
                project_complexity = "high"
            elif project.priority <= 3:
                project_complexity = "medium"
            else:
                project_complexity = "low"
            
            # Detectar skills relevantes
            detected_skills = required_skills[:5] if required_skills else ["No especificados"]
            
            return {
                "suggested_title": f"Evaluación {project.title}",
                "suggested_description": f"Evaluación técnica para proyecto {project.title} - Nivel {difficulty.lower()}",
                "suggested_type": assessment_type,
                "suggested_difficulty": difficulty,
                "suggested_time_minutes": time_minutes,
                "suggested_passing_score": passing_score,
                "suggested_num_questions": num_questions,
                "suggested_programming_language": programming_language if assessment_type == "CODING" else None,
                "difficulty_reason": f"Match score de {application.match_score}% sugiere nivel {difficulty}",
                "time_reason": f"Dificultad {difficulty} requiere aproximadamente {time_minutes} minutos",
                "score_reason": f"Score mínimo de {passing_score}% apropiado para nivel {difficulty}",
                "type_reason": f"{'Skills de programación detectados' if has_coding else 'Skills principalmente teóricos'} sugieren {assessment_type}",
                "detected_skills": detected_skills,
                "candidate_experience_level": candidate_experience,
                "project_complexity": project_complexity,
                "application_id": application_id,
                "analyzed_at": datetime.datetime.now().isoformat(),
                "fallback_used": True
            }
            
        except Application.DoesNotExist:
            raise ValueError(f"Application {application_id} no encontrada")
        except Exception as e:
            raise Exception(f"Error en fallback: {str(e)}")