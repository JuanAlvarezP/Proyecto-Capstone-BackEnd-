# 🚀 Quick Start - Endpoint de Sandbox

## 📍 URL del Endpoint

```
POST /api/assessments/answers/{answer_id}/evaluate_code_sandbox/
```

**URL completa:** `http://localhost:8000/api/assessments/answers/{answer_id}/evaluate_code_sandbox/`

## 🔑 Headers Requeridos

```javascript
{
  'Content-Type': 'application/json',
  'Authorization': 'Bearer YOUR_JWT_TOKEN'
}
```

## 📦 Body del Request

```javascript
{
  "test_results": [
    {
      "test_case": "Descripción del test",
      "input": "entrada del test",
      "expected_output": "salida esperada",
      "actual_output": "salida real",
      "passed": true,  // boolean
      "execution_time_ms": 1.23,  // float
      "error": null  // string o null
    }
  ],
  "total_tests": 3,  // int: total de tests
  "passed_tests": 2,  // int: tests que pasaron
  "sandbox_success": true  // boolean: si el sandbox funcionó
}
```

## 📤 Ejemplo de Respuesta

```javascript
{
  "id": 1,
  "question": {
    "id": 1,
    "question_text": "Implementa una función que sume los números pares...",
    "programming_language": "python"
  },
  "candidate": 1,
  "code_answer": "def suma_pares(arr):\n    return sum(x for x in arr if x % 2 == 0)",
  "is_correct": true,  // boolean: si pasó todos los tests
  "points_earned": 85,  // float: puntaje final (0-100)
  "feedback": "🔒 **Evaluación con Sandbox...**\n✅ Tests pasados: 3/3\n...",
  "test_results": [...],  // array: los test_results que enviaste
  "answered_at": "2025-12-17T10:30:00Z"
}
```

## 💡 Integración Frontend

### Ejemplo con Fetch API

```javascript
async function evaluateCodeWithSandbox(answerId, sandboxResults) {
  const response = await fetch(
    `http://localhost:8000/api/assessments/answers/${answerId}/evaluate_code_sandbox/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${yourJwtToken}`
      },
      body: JSON.stringify({
        test_results: sandboxResults.test_results,
        total_tests: sandboxResults.total_tests,
        passed_tests: sandboxResults.passed_tests,
        sandbox_success: sandboxResults.sandbox_success
      })
    }
  );
  
  const data = await response.json();
  return data;
}
```

### Ejemplo con Axios

```javascript
import axios from 'axios';

const evaluateCodeWithSandbox = async (answerId, sandboxResults) => {
  try {
    const { data } = await axios.post(
      `/api/assessments/answers/${answerId}/evaluate_code_sandbox/`,
      {
        test_results: sandboxResults.test_results,
        total_tests: sandboxResults.total_tests,
        passed_tests: sandboxResults.passed_tests,
        sandbox_success: sandboxResults.sandbox_success
      },
      {
        headers: {
          'Authorization': `Bearer ${yourJwtToken}`
        }
      }
    );
    
    return data;
  } catch (error) {
    console.error('Error evaluando código:', error.response?.data);
    throw error;
  }
};
```

## ⚙️ Lógica de Calificación

```
Score Final = Funcionalidad (70%) + Calidad (30%)

Funcionalidad = (tests_pasados / total_tests) * 70
Calidad = Evaluación IA (0-30)

Mínimo garantizado: 70% si pasa todos los tests
```

## ⚠️ Importante

1. **answerId**: Debe ser el ID de un `CandidateAnswer` existente
2. **sandbox_success**: Si es `false` o `total_tests` es 0, el sistema automáticamente usa evaluación tradicional con IA
3. **Autenticación**: El token JWT debe ser válido y pertenecer al candidato o un admin

## 🧪 Testing Rápido

```bash
# 1. Obtén un token JWT (login)
# 2. Crea o encuentra un answer_id
# 3. Ejecuta:

curl -X POST http://localhost:8000/api/assessments/answers/1/evaluate_code_sandbox/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer tu_token_aqui" \
  -d '{
    "test_results": [{
      "test_case": "Test básico",
      "input": "[1,2,3]",
      "expected_output": "6",
      "actual_output": "6",
      "passed": true,
      "execution_time_ms": 1.0,
      "error": null
    }],
    "total_tests": 1,
    "passed_tests": 1,
    "sandbox_success": true
  }'
```

---

✅ **Backend listo para consumir desde el frontend**
