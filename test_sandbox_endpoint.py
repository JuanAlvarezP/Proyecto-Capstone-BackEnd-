"""
Script de prueba para el endpoint evaluate_code_sandbox
Ejecutar con: python test_sandbox_endpoint.py
"""

import requests
import json

# Configuración
BASE_URL = "http://localhost:8000"
# Debes reemplazar estos valores con datos reales de tu BD
ANSWER_ID = 1  # ID de una respuesta existente
TOKEN = "tu_token_jwt_aqui"  # Token de autenticación

# Datos de prueba simulando la respuesta del sandbox
test_data = {
    "test_results": [
        {
            "test_case": "Suma de números pares",
            "input": "[1, 2, 3, 4, 5, 6]",
            "expected_output": "12",
            "actual_output": "12",
            "passed": True,
            "execution_time_ms": 1.5,
            "error": None
        },
        {
            "test_case": "Array vacío",
            "input": "[]",
            "expected_output": "0",
            "actual_output": "0",
            "passed": True,
            "execution_time_ms": 0.8,
            "error": None
        },
        {
            "test_case": "Solo números impares",
            "input": "[1, 3, 5, 7]",
            "expected_output": "0",
            "actual_output": "0",
            "passed": True,
            "execution_time_ms": 1.0,
            "error": None
        }
    ],
    "total_tests": 3,
    "passed_tests": 3,
    "sandbox_success": True
}

def test_evaluate_code_sandbox():
    """Prueba el endpoint de evaluación con sandbox"""
    
    url = f"{BASE_URL}/api/assessments/answers/{ANSWER_ID}/evaluate_code_sandbox/"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }
    
    try:
        print(f"📡 Enviando petición a: {url}")
        print(f"📦 Datos: {json.dumps(test_data, indent=2)}")
        
        response = requests.post(url, json=test_data, headers=headers)
        
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"📄 Respuesta:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: No se pudo conectar al servidor.")
        print("   Asegúrate de que el servidor Django esté corriendo (python manage.py runserver)")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST: Endpoint evaluate_code_sandbox")
    print("=" * 60)
    print()
    print("⚠️  ANTES DE EJECUTAR:")
    print("1. Asegúrate de que el servidor Django esté corriendo")
    print("2. Edita este archivo y configura:")
    print("   - ANSWER_ID: ID de una respuesta existente")
    print("   - TOKEN: Tu token JWT válido")
    print()
    
    # Preguntar si continuar
    response = input("¿Continuar con la prueba? (s/n): ")
    if response.lower() == 's':
        test_evaluate_code_sandbox()
    else:
        print("❌ Prueba cancelada")
