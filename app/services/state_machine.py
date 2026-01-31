import re
import os
from datetime import datetime
from app.domain.states import ConversationState

# =========================
# CONFIG
# =========================

ORDERS_DIR = "orders"

if not os.path.exists(ORDERS_DIR):
    os.makedirs(ORDERS_DIR)

# =========================
# HELPERS
# =========================

def _format_items(items):
    lines = []
    for it in items or []:
        qty = it.get("qty", 0)
        name = it.get("name", "")
        if name:
            lines.append(f"- {qty} {name}")
    return "\n".join(lines) if lines else "- (sin items)"

def _build_summary(data):
    return (
        "🧾 *Resumen del pedido*\n"
        f"{_format_items(data.get('items', []))}\n\n"
        f"🚚 Modalidad: {data.get('delivery_method','-')}\n"
        f"📍 Dirección: {data.get('address','-')}\n"
        f"💳 Pago: {data.get('payment_method','-')}\n"
        f"🙋 Nombre: {data.get('name','-')}\n\n"
        "¿Confirmás? (si / no)"
    )

def save_order_txt(data):
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{ORDERS_DIR}/order_{now}.txt"

    content = (
        "===== NUEVO PEDIDO =====\n"
        f"Fecha: {now}\n\n"
        f"{_build_summary(data)}\n"
        "========================\n"
    )

    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

# =========================
# MAIN FSM
# =========================

def handle_message(state, text, data):
    text = (text or "").lower().strip()

    # -------- NEW ----------
    if state == ConversationState.NEW:
        return (
            ConversationState.GREETING,
            {},
            "Hola! Soy Vendobot 🤖 ¿Querés hacer un pedido?"
        )

    # -------- GREETING ----------
    if state == ConversationState.GREETING:
        state = ConversationState.AWAITING_ORDER

    # -------- AWAITING_ORDER ----------
    if state == ConversationState.AWAITING_ORDER:

        def clean_item_name(s):
            s = s.lower()
            s = s.replace("+", " ")
            s = re.sub(r"\b(y|con|de|del|la|el|los|las)\b", " ", s)
            s = re.sub(r"\s+", " ", s).strip()

            if s in ["hamb", "ham", "hambur"]:
                s = "hamburguesa"

            return s

        items = []
        matches = re.findall(r"(\d+)\s+([a-zA-Záéíóúñü ]+)", text)

        for qty, name in matches:
            name = clean_item_name(name)
            items.append({
                "name": name,
                "qty": int(qty)
            })

        if not items:
            return (
                ConversationState.AWAITING_ORDER,
                data,
                "No entendí 😕 Probá: 2 hamburguesas y 1 coca"
            )

        data["items"] = items

        return (
            ConversationState.ASK_DELIVERY,
            data,
            "Genial 👍 ¿Es para retiro o envío?"
        )

    # -------- ASK_DELIVERY ----------
    if state == ConversationState.ASK_DELIVERY:

        if any(w in text for w in ["envio", "envío", "domicilio"]):
            data["delivery_method"] = "envio"
        elif any(w in text for w in ["retiro", "buscar", "paso"]):
            data["delivery_method"] = "retiro"
        else:
            return (
                ConversationState.ASK_DELIVERY,
                data,
                "¿Retiro o envío?"
            )

        if data["delivery_method"] == "envio":
            return (
                ConversationState.ASK_ADDRESS,
                data,
                "Pasame tu dirección"
            )

        return (
            ConversationState.ASK_PAYMENT,
            data,
            "¿Pagás en efectivo o transferencia?"
        )

    # -------- ASK_ADDRESS ----------
    if state == ConversationState.ASK_ADDRESS:

        if len(text) < 5:
            return (
                ConversationState.ASK_ADDRESS,
                data,
                "Dirección más completa por favor"
            )

        data["address"] = text

        return (
            ConversationState.ASK_PAYMENT,
            data,
            "¿Pagás en efectivo o transferencia?"
        )

    # -------- ASK_PAYMENT ----------
    if state == ConversationState.ASK_PAYMENT:

        if "efectivo" in text:
            data["payment_method"] = "efectivo"
        elif any(w in text for w in ["transfer", "mp", "mercado"]):
            data["payment_method"] = "transferencia"
        else:
            return (
                ConversationState.ASK_PAYMENT,
                data,
                "Efectivo o transferencia?"
            )

        return (
            ConversationState.ASK_NAME,
            data,
            "¿A nombre de quién?"
        )

    # -------- ASK_NAME ----------
    if state == ConversationState.ASK_NAME:

        if len(text) < 2:
            return (
                ConversationState.ASK_NAME,
                data,
                "Decime un nombre válido"
            )

        data["name"] = text

        return (
            ConversationState.ASK_CONFIRM,
            data,
            _build_summary(data)
        )

    # -------- ASK_CONFIRM ----------
    if state == ConversationState.ASK_CONFIRM:

        if text in ["si", "sí", "ok", "dale", "confirmo"]:
            save_order_txt(data)
            return (
                ConversationState.DONE,
                data,
                "Pedido confirmado ✅ En breve te confirmo el total."
            )

        if text in ["no", "cancelar"]:
            return (
                ConversationState.AWAITING_ORDER,
                {},
                "Perfecto, arrancamos de nuevo. ¿Qué querés pedir?"
            )

        return (
            ConversationState.ASK_CONFIRM,
            data,
            "Respondé si o no"
        )

    # -------- DONE ----------
    if state == ConversationState.DONE:
        return (
            ConversationState.NEW,
            {},
            "Si querés hacer otro pedido escribí hola 🙂"
        )

    # -------- FALLBACK ----------
    return (
        ConversationState.NEW,
        {},
        "Escribí hola para empezar"
    )
