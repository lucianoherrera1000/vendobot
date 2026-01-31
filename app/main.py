from flask import Flask, jsonify, request

from app.db.conn import init_db
from app.db.repository import get_session, reset_session, upsert_session
from app.services.state_machine import StateMachine
from app.domain.states import ConversationState

app = Flask(__name__)

# Inicializa DB al levantar
init_db()

sm = StateMachine()


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/debug/reset/<phone>")
def debug_reset(phone: str):
    existed = reset_session(phone)
    return jsonify(
        {
            "ok": True,
            "phone": phone,
            "message": "Sesión borrada" if existed else "No existía",
        }
    )


@app.post("/debug/step")
def debug_step():
    payload = request.get_json(force=True) or {}
    phone = payload.get("phone", "test")
    text = payload.get("text", "")

    # Si force_state=true, usás el estado/data del payload.
    # Si no, siempre continúa desde lo guardado en DB.
    force_state = bool(payload.get("force_state", False))

    if force_state:
        state = payload.get("state", ConversationState.NEW)
        data = payload.get("data") or {}
        state_used = state
    else:
        state, data = get_session(phone)
        state_used = state

    result = sm.handle_message(state=state, text=text, data=data)

    # Guardar sesión actualizada
    upsert_session(phone, result.next_state, result.data)

    return jsonify(
        {
            "data": result.data,
            "next_state": result.next_state,
            "reply_text": result.reply_text,
            "state_used": state_used,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
