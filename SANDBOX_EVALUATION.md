# Evaluación de Código con Sandbox - Documentación

## 📋 Descripción General

Se ha implementado un nuevo sistema de evaluación **híbrido** para código que combina:

- **70% - Funcionalidad**: Basado en resultados reales de ejecución en sandbox
- **30% - Calidad**: Evaluación de IA sobre legibilidad, eficiencia y buenas prácticas

## 🎯 Ventajas del Sistema Híbrido

✅ **Más Objetivo**: La mayoría del puntaje (70%) proviene de tests reales, no de interpretación de IA
✅ **Más Justo**: Si el código pasa todos los tests, garantiza mínimo 70% de calificación
✅ **Menos Costos**: Solo se usa IA para evaluar calidad (30%), reduciendo llamadas a OpenAI
✅ **Más Rápido**: Ejecución de tests es instantánea
✅ **Más Confiable**: No depende de interpretación subjetiva de IA

## 🔧 Implementación Backend

### Archivos Modificados

#### 1. `/assessments/views.py`

**Imports agregados:**

```python
from django.conf import settings
import json
import logging

logger = logging.getLogger(__name__)
```

**Nuevo método en `CandidateAnswerViewSet`:**

```python
@action(detail=True, methods=['post'])
def evaluate_code_sandbox(self, request, pk=None):
```

### 2. Endpoint Disponible

**URL:** `POST /api/assessments/answers/{id}/evaluate_code_sandbox/`

**Autenticación:** Requerida (JWT Token)

**Body esperado:**

```json
{
  "test_results": [
    {
      "test_case": "Descripción del test",
      "input": "Datos de entrada",
      "expected_output": "Salida esperada",
      "actual_output": "Salida obtenida",
      "passed": true,
      "execution_time_ms": 1.23,
      "error": null
    }
  ],
  "total_tests": 3,
  "passed_tests": 2,
  "sandbox_success": true
}
```

**Respuesta:**

```json
{
    "id": 1,
    "question": {
        "id": 1,
        "question_text": "Implementa una función...",
        "programming_language": "python"
    },
    "candidate": 1,
    "code_answer": "def suma_pares(arr):...",
    "is_correct": true,
    "points_earned": 85,
    "feedback": "🔒 **Evaluación con Sandbox (ejecución real)**\n✅ Tests pasados: 3/3\n\n...",
    "test_results": [...],
    "answered_at": "2025-12-17T10:30:00Z"
}
```

## 📊 Lógica de Calificación

### 1. Cálculo de Funcionalidad (70%)

```python
functionality_score = (passed_tests / total_tests) * 70
```

### 2. Evaluación de Calidad con IA (30%)

La IA evalúa **SOLO** calidad, NO funcionalidad:

- **Legibilidad**: ¿Es fácil de entender?
- **Eficiencia**: ¿Usa buen algoritmo?
- **Buenas Prácticas**: ¿Sigue convenciones?

Puntaje: 0-30 puntos

### 3. Score Final

```python
final_score = functionality_score + quality_score

# Garantía de mínimos
if is_correct and final_score < 70:
    final_score = 70  # Mínimo si pasa todos los tests
```

## 🔄 Flujo de Trabajo

```
┌─────────────────────────────────────────────┐
│  Frontend ejecuta código en Sandbox        │
│  (e0, Piston API, u otro servicio)         │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  Frontend recopila resultados de tests:    │
│  - Test 1: ✅ Pasado                       │
│  - Test 2: ✅ Pasado                       │
│  - Test 3: ❌ Fallido                      │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  POST /api/.../evaluate_code_sandbox/      │
│  Body: {                                    │
│    test_results: [...],                     │
│    total_tests: 3,                          │
│    passed_tests: 2,                         │
│    sandbox_success: true                    │
│  }                                          │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  Backend calcula:                           │
│  1. Funcionalidad = 2/3 * 70 = 46.67%      │
│  2. IA evalúa calidad = 22/30               │
│  3. Score final = 46.67 + 22 = 68.67%      │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  Backend actualiza CandidateAnswer:         │
│  - is_correct: false                        │
│  - points_earned: 68.67                     │
│  - feedback: "🔒 Evaluación con Sandbox..." │
│  - test_results: [...]                      │
└─────────────────────────────────────────────┘
```

## 🧪 Testing

### Prueba Manual con cURL

```bash
curl -X POST http://localhost:8000/api/assessments/answers/1/evaluate_code_sandbox/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "test_results": [
      {
        "test_case": "Suma de números pares",
        "input": "[1,2,3,4,5,6]",
        "expected_output": "12",
        "actual_output": "12",
        "passed": true,
        "execution_time_ms": 1.5,
        "error": null
      }
    ],
    "total_tests": 1,
    "passed_tests": 1,
    "sandbox_success": true
  }'
```

### Script de Prueba Python

Se incluye `test_sandbox_endpoint.py` para pruebas automatizadas.

```bash
# Editar el archivo y configurar ANSWER_ID y TOKEN
python test_sandbox_endpoint.py
```

## 📝 Modelo de Datos

### Campo `test_cases` en Question

Ya existe en el modelo:

```python
test_cases = JSONField(default=list, blank=True,
                       help_text="Casos de prueba para validar código")
```

**Formato esperado:**

```python
[
    {
        "description": "Suma de números pares en [1,2,3,4,5,6]",
        "input": "[1,2,3,4,5,6]",
        "expected_output": "12"
    },
    {
        "description": "Array vacío",
        "input": "[]",
        "expected_output": "0"
    }
]
```

### Campo `test_results` en CandidateAnswer

Ya existe en el modelo:

```python
test_results = JSONField(default=dict, blank=True,
                         help_text="Resultados de test cases")
```

## ⚙️ Configuración Requerida

### 1. Variables de Entorno

En `.env`:

```env
OPENAI_API_KEY=sk-...
```

### 2. Dependencias

```bash
pip install openai
```

Ya instalado: `openai 2.8.0`

### 3. Migraciones

No se requieren nuevas migraciones. Los campos necesarios ya existen:

- `Question.test_cases` ✅
- `CandidateAnswer.test_results` ✅
- `CandidateAnswer.code_answer` ✅

## 🔐 Permisos

El endpoint `evaluate_code_sandbox` es accesible por:

- ✅ Usuarios autenticados (cualquier rol)
- ✅ El candidato dueño de la respuesta
- ✅ Administradores

## 📊 Feedback Generado

El sistema genera feedback estructurado con:

1. **Resultados de Ejecución:**

   ```
   🔒 Evaluación con Sandbox (ejecución real)
   ✅ Tests pasados: 2/3

   ✅ Test 1: Suma de números pares
      Input: [1,2,3,4,5,6]
      Esperado: 12
      Obtenido: 12

   ❌ Test 2: Array vacío
      Input: []
      Esperado: 0
      Obtenido: null
      Error: TypeError: ...
   ```

2. **Evaluación de Calidad (IA):**

   ```
   🤖 Evaluación de Calidad (IA)
   El código muestra buena legibilidad con nombres descriptivos...
   ```

3. **Resumen:**
   ```
   📊 Desglose de puntaje:
   - Funcionalidad (tests): 46.7/70
   - Calidad (código): 22.0/30
   - Total: 68.7/100
   ```

## 🔄 Fallback a Evaluación Tradicional

Si `sandbox_success = false` o `total_tests = 0`:

```python
if not sandbox_success or total_tests == 0:
    return self.evaluate_code(request, pk)
```

El sistema automáticamente usa el método anterior (`evaluate_code`) basado 100% en IA.

## 🚀 Próximos Pasos

1. ✅ Endpoint implementado
2. ✅ Validaciones completadas
3. ✅ Migraciones aplicadas
4. ⏳ Integración con frontend
5. ⏳ Pruebas end-to-end

## 📚 Referencias

- Modelo OpenAI: `gpt-4o-mini`
- Temperature para calidad: `0.6` (balance entre creatividad y consistencia)
- Formato respuesta: `json_object` (garantiza JSON válido)

---

**Fecha de implementación:** 17 de diciembre de 2025  
**Versión backend:** Django 5.2.7 + DRF 3.15.2  
**Estado:** ✅ Implementado y listo para integración
