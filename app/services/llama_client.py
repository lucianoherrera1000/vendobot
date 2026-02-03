# app/services/llama_client.py
import os
import json
import re
import requests

AI_ENABLED = os.getenv("AI_ENABLED", "0").strip() == "1"
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
LLAMA_MODEL = os.getenv("LLAMA_MODEL", "model.gguf").strip()  # podés dejarlo vacío si querés


def _extract_first_json(s: str):
    if not s:
        return None
    # buscamos el primer objeto JSON {...}
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not m:
        return None
    candidate = m.group(0).strip()
    try:
        return json.loads(candidate)
    except Exception:
        return None


def llama_extract(user_text: str):
    """
    Devuelve dict:
      {"ok": True, "items":[{"name":"coca","qty":1}], "delivery_method":..., "address":..., "payment_method":..., "name":...}
    """
    if not AI_ENABLED:
        return {"ok": False}

    prompt = (
        "Devolvé SOLO JSON válido, sin texto extra.\n"
        "Formato exacto:\n"
        "{\"ok\":true,\"items\":[{\"name\":\"...\",\"qty\":1}]}\n"
        "Reglas:\n"
        "- items: lista de productos. qty entero. si no hay qty asumí 1.\n"
        "- NO escribas explicaciones.\n"
        "- NO agregues ejemplos.\n"
        f"Usuario: {user_text}\n"
        "JSON:\n"
    )

    payload = {
        "model": LLAMA_MODEL if LLAMA_MODEL else "model.gguf",
        "prompt": prompt,
        "temperature": 0,
        "max_tokens": 120,
        # stops para cortar cuando empieza a inventar “Usuario: ...”
        "stop": ["\n\nUsuario:", "\nUsuario:", "\nJSON:"]
    }

    try:
        r = requests.post(f"{LLAMA_BASE_URL}/v1/completions", json=payload, timeout=30)
        r.raise_for_status()
        js = r.json()
        text = (js.get("choices") or [{}])[0].get("text", "")
        obj = _extract_first_json(text)
        if isinstance(obj, dict) and obj.get("ok") is True:
            return obj
        return {"ok": False}
    except Exception:
        return {"ok": False}
