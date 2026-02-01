import json
import requests

# Ajustá esto si tu llama-server escucha otro puerto
LLAMA_BASE_URL = "http://127.0.0.1:8080"

SYSTEM_PROMPT = """
Sos un extractor de información para un bot de pedidos de comida.
Tu única salida debe ser JSON válido (sin texto extra, sin markdown).
No inventes datos: si no está, devolvé null.

Campos permitidos:
- intent: "order" | "menu_question" | "greeting" | "other"
- items: lista de { "name": string, "qty": int|null }
- delivery_method: "envio" | "retiro" | null
- address: string|null
- payment_method: "efectivo" | "transferencia" | null
- name: string|null
- menu_query: string|null   (si pregunta por un producto: "fideos", "coca", etc.)
- confidence: number (0 a 1)

Reglas:
- Si el usuario dice "tienen X?" o "hay X?" => intent="menu_question" y menu_query="x"
- Si hay intención de pedido pero sin cantidad ("quiero hamburguesa") => intent="order", qty=null
- Si sólo saluda => intent="greeting"
"""

def llama_extract(user_text: str, menu_text: str = "") -> dict | None:
    """
    Llama a un servidor tipo llama.cpp con endpoint OpenAI-compatible:
      POST /v1/chat/completions
    Si tu server no soporta ese endpoint, avisame y lo adapto al endpoint real.
    """
    url = f"{LLAMA_BASE_URL}/v1/chat/completions"
    payload = {
        "model": "local-model",
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.strip()},
            {"role": "user", "content": f"MENU:\n{menu_text}\n\nMENSAJE:\n{user_text}"}
        ],
        "stream": False
    }

    try:
        r = requests.post(url, json=payload, timeout=20)
        r.raise_for_status()
        data = r.json()

        # OpenAI style: choices[0].message.content
        content = data["choices"][0]["message"]["content"].strip()

        # A veces vienen backticks: los limpiamos
        content = content.strip("` \n")

        obj = json.loads(content)
        return obj
    except Exception as e:
        print("[AI] extract failed:", str(e))
        return None
