import os
import time
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify

from app.services.state_machine import handle_message
from app.domain.states import ConversationState

# =========================
# ENV
# =========================
load_dotenv()

APP_NAME = os.getenv("APP_NAME", "VENDOBOT")

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID", "")

# =========================
# FLASK
# =========================
app = Flask(__name__)

# memoria simple en RAM (por teléfono)
sessions = {}

# dedupe simple para webhooks (evita respuestas duplicadas)
# guardamos msg_id -> timestamp, y limpiamos por TTL
SEEN_MSG_TTL_SEC = 60 * 10
seen_msg_ids = {}  # { "wamid.xxx": 1700000000.0 }

def _seen_before(msg_id: str) -> bool:
    if not msg_id:
        return False
    now = time.time()
    # cleanup ocasional
    if len(seen_msg_ids) > 500:
        cutoff = now - SEEN_MSG_TTL_SEC
        for k, ts in list(seen_msg_ids.items()):
            if ts < cutoff:
                seen_msg_ids.pop(k, None)

    if msg_id in seen_msg_ids:
        return True

    seen_msg_ids[msg_id] = now
    return False


def get_session(phone: str):
    if phone not in sessions:
        sessions[phone] = {
            "state": ConversationState.NEW,
            "data": {}
        }
    return sessions[phone]


def send_whatsapp_text(to_phone: str, text: str):
    """
    Envía un mensaje de texto usando WhatsApp Cloud API.
    Requiere:
      - WHATSAPP_TOKEN
      - PHONE_NUMBER_ID
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        print("[WARN] WHATSAPP_TOKEN o PHONE_NUMBER_ID faltante. No envío nada.")
        return

    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": text}
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code >= 400:
            print("[ERROR] WhatsApp send failed:", r.status_code, r.text)
        else:
            print("[OK] WhatsApp send:", r.status_code)
    except Exception as e:
        print("[ERROR] WhatsApp send exception:", str(e))


# =========================
# HEALTH
# =========================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "app": APP_NAME,
        "env_loaded": True,
        "has_verify_token": bool(VERIFY_TOKEN),
        "has_whatsapp_token": bool(WHATSAPP_TOKEN),
        "has_phone_number_id": bool(PHONE_NUMBER_ID),
    })


# =========================
# WEBHOOK META (WhatsApp)
# =========================
@app.route("/webhook", methods=["GET"])
def webhook_verify():
    """
    Meta Webhook Verification
    Meta manda:
      hub.mode=subscribe
      hub.verify_token=...
      hub.challenge=...
    """
    mode = request.args.get("hub.mode", "")
    token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Forbidden", 403


@app.route("/webhook", methods=["POST"])
def webhook_receive():
    """
    Recibe eventos de WhatsApp Cloud API.
    Extrae texto entrante y responde con tu state_machine.
    """
    payload = request.get_json(silent=True) or {}

    try:
        entry = payload.get("entry", [])
        for e in entry:
            changes = e.get("changes", [])
            for ch in changes:
                value = ch.get("value", {})

                messages = value.get("messages", [])
                if not messages:
                    continue

                for msg in messages:
                    msg_id = msg.get("id", "")
                    if _seen_before(msg_id):
                        # evita respuestas duplicadas
                        continue

                    from_phone = msg.get("from")  # numero del cliente (string)
                    msg_type = msg.get("type", "")

                    # Solo soportamos texto por ahora (si no es texto, lo ignoramos)
                    if msg_type != "text":
                        continue

                    text = (msg.get("text", {}) or {}).get("body", "")
                    text = (text or "").strip()

                    # Si llega vacío, no hagas nada (evita "No entendí" fantasma)
                    if not from_phone or not text:
                        continue

                    session = get_session(from_phone)
                    state = session["state"]
                    data = session["data"]

                    next_state, new_data, reply_text = handle_message(state, text, data)

                    session["state"] = next_state
                    session["data"] = new_data

                    if reply_text:
                        send_whatsapp_text(from_phone, reply_text)

        return jsonify({"ok": True}), 200

    except Exception as e:
        print("[ERROR] webhook_receive exception:", str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


# =========================
# DEBUG ENDPOINTS
# =========================
@app.route("/debug/reset/<phone>", methods=["POST"])
def reset(phone):
    sessions.pop(phone, None)
    return jsonify({"ok": True, "phone": phone})


@app.route("/debug/step", methods=["POST"])
def debug_step():
    payload = request.get_json() or {}
    phone = payload.get("phone", "")
    text = payload.get("text", "")

    session = get_session(phone)
    state = session["state"]
    data = session["data"]

    next_state, new_data, reply = handle_message(state, text, data)

    session["state"] = next_state
    session["data"] = new_data

    return jsonify({
        "state_used": state,
        "next_state": next_state,
        "reply_text": reply,
        "data": new_data
    })


# =========================
# RUN
# =========================
if __name__ == "__main__":
    # IMPORTANTE:
    # - use_reloader=False evita doble ejecución en debug (y mensajes duplicados)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

