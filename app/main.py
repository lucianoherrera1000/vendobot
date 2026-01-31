from flask import Flask, request, jsonify

from app.services.state_machine import handle_message
from app.domain.states import ConversationState

app = Flask(__name__)

# memoria simple en RAM
sessions = {}


def get_session(phone):
    if phone not in sessions:
        sessions[phone] = {
            "state": ConversationState.NEW,
            "data": {}
        }
    return sessions[phone]


@app.route("/debug/reset/<phone>", methods=["POST"])
def reset(phone):
    sessions.pop(phone, None)
    return jsonify({"ok": True, "phone": phone})


@app.route("/debug/step", methods=["POST"])
def debug_step():
    payload = request.get_json()

    phone = payload["phone"]
    text = payload["text"]

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


if __name__ == "__main__":
    app.run(debug=True)

