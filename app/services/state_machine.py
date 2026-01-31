import re
from app.domain.states import ConversationState


def handle_message(state, text, data):
    text = text.lower().strip()

    # -------- NEW ----------
    if state == ConversationState.NEW:
        return (
            ConversationState.GREETING,
            {},
            "Hola! Soy Vendobot 🤖 ¿Querés hacer un pedido?"
        )

    # -------- GREETING (se comporta como pedido) ----------
    if state == ConversationState.GREETING:
        state = ConversationState.AWAITING_ORDER

    # -------- AWAITING_ORDER ----------
    if state == ConversationState.AWAITING_ORDER:

        items = []

        matches = re.findall(r"(\d+)\s+([a-zA-Záéíóúñ ]+)", text)

        for qty, name in matches:
            items.append({
                "name": name.strip(),
                "qty": int(qty)
            })

        if not items:
            return (
                ConversationState.AWAITING_ORDER,
                data,
                "No entendí el pedido 😕 Probá: 2 hamburguesas y 1 coca"
            )

        data["items"] = items

        return (
            ConversationState.ASK_DELIVERY,
            data,
            "Genial 👍 ¿Es para retiro o envío?"
        )

    # -------- ASK_DELIVERY ----------
    if state == ConversationState.ASK_DELIVERY:

        if "envio" in text:
            data["delivery_method"] = "envio"
        elif "retiro" in text:
            data["delivery_method"] = "retiro"
        else:
            return (
                ConversationState.ASK_DELIVERY,
                data,
                "Decime si es retiro o envío"
            )

        if data["delivery_method"] == "envio":
            return (
                ConversationState.ASK_ADDRESS,
                data,
                "Pasame tu dirección completa"
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
                "Pasame una dirección válida"
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
        elif "transfer" in text:
            data["payment_method"] = "transferencia"
        else:
            return (
                ConversationState.ASK_PAYMENT,
                data,
                "Decime efectivo o transferencia"
            )

        return (
            ConversationState.ASK_NAME,
            data,
            "¿A nombre de quién preparo el pedido?"
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
            ConversationState.DONE,
            data,
            "Listo ✅ Tomé tu pedido. En breve te confirmo el total."
        )

    # -------- FALLBACK ----------
    return (
        ConversationState.NEW,
        {},
        "Arranquemos de nuevo. Escribí hola."
    )

