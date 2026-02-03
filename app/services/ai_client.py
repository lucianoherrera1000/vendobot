import os
import json
import requests

LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8080")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "model")
LLAMA_TIMEOUT = int(os.getenv("LLAMA_TIMEOUT", "20"))

SYSTEM_PROMPT = """Sos un extractor de datos para un bot de ventas.
Tu tarea: devolver SOLO JSON válido, sin texto extra.

De un mensaje del cliente, extraé si podés:
- items: lista de {name, qty}
- delivery_method: "envio" o "retiro"
- address: string
- payment_method: "efectivo" o "transferencia"
- name: string

Si no encontrás nada, devolvé: {"ok":false}
Si encontrás algo, devolvé: {"ok":true, ...campos...}

Reglas:
- qty default 1 si el usuario pide 1 cosa sin número (ej: "una coca" -> qty 1)
- nombres en minúscula
- no inventes items
"""

def llama_extract(text: str) -> dict:
    if not text:
        return {"ok": False}

    url = f"{LLAMA_BASE_URL}/v1/chat/completions"
    payload = {
        "model": LLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "temperature": 0,
    }

    try:
        r = requests.post(url, json=payload, timeout=LLAMA_TIMEOUT)
        if r.status_code >= 400:
            return {"ok": False, "error": f"{r.status_code} {r.text}"}

        data = r.json()
        content = data["choices"][0]["message"]["content"].strip()

        # el modelo debe devolver JSON directo
        out = json.loads(content)
        if isinstance(out, dict):
            return out
        return {"ok": False}

    except Exception as e:
        return {"ok": False, "error": str(e)}

