import re
from app.domain.states import ConversationState


def _format_items(items):
    lines = []
    for it in items or []:
        qty = it.get("qty", 0)
        name = it.get("name", "")
        if name:
            lines.append(f"- {qty} {name}")
    return "\n".join(lines) if lines else "- (sin items)"


def _build_summary(data):
    items_txt = _format_items(data.get("items", []))

    delivery = data.get("delivery_method")
    if delivery == "envio":
        delivery_txt = "Envío"
    elif delivery == "retiro":
        delivery_txt = "Retiro"
    else:
        delivery_txt = "(sin definir)"

    address = data.get("address")
    address_txt = address if address else "-"

    pay = data.get("payment_method")
    if pay == "efectivo":
        pay_txt = "Efectivo"
    elif pay == "transferencia":
        pay_txt = "Transferencia"
    else:
        pay_txt = "(sin definir)"

    name = data.get("name", "-")

    return (
        "🧾 *Resumen del pedido*\n"
        f"{items_txt}\n\n"
        f"🚚 Modalidad: {delivery_txt}\n"
        f"📍 Dirección: {address_txt}\n"
        f"💳 Pago: {pay_txt}\n"
        f"🙋 Nombre: {name}\n\n"
        "¿Confirmás? (si / no)"
    )


def handle_message(state, text, data):
    text = (text or "").lower().strip()

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

        def clean_item_name(s: str) -> str:
            s = (s or "").lower().strip()

            # separadores comunes → espacio
            s = s.replace("+", " ")
            s = re.sub(r"\s+", " ", s)

            # sacar conectores como palabras completas
            s = re.sub(r"\b(y|con|de|del|la|el|los|las)\b", " ", s)

            # limpiar espacios repetidos
            s = re.sub(r"\s+", " ", s).strip()

            # sacar puntuación al final
            s = re.sub(r"[.,;:]+$", "", s).strip()

            # mini-normalizaciones (opcional)
            # "hamb" => "hamburguesa"
            if s in ("hamb", "ham", "hambur", "hamburg"):
                s = "hamburguesa"

            return s

        items = []

        # Acepta: "2 hamburguesas", "1 coca", también con + o con y en el medio.
        matches = re.findall(r"(\d+)\s+([a-zA-ZáéíóúñüÁÉÍÓÚÑÜ ]+)", text)

        for qty, name in matches:
            name = clean_item_name(name)
            if not name:
                continue
            items.append({
                "name": name,
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
        if any(x in text for x in ["envio", "envío", "a domicilio", "domicilio", "mandalo", "mandámelo"]):
            data["delivery_method"] = "envio"
        elif any(x in text for x in ["retiro", "retirar", "paso a buscar", "voy a buscar", "busco", "buscar"]):
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
        # dirección demasiado corta => repregunta
        if len(text) < 5:
            return (
                ConversationState.ASK_ADDRESS,
                data,
                "Me pasás la dirección completa? (calle + número, y si hay dpto/barrio mejor)"
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
        elif any(x in text for x in ["transfer", "transf", "mercado pago", "mp", "alias", "cbu"]):
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
        # si el usuario vuelve a decir "transferencia" acá, NO lo tomamos como nombre
        if any(x in text for x in ["transfer", "transf", "mercado pago", "mp"]):
            return (
                ConversationState.ASK_NAME,
                data,
                "Perfecto. Ahora decime tu nombre 🙂"
            )

        if len(text) < 2:
            return (
                ConversationState.ASK_NAME,
                data,
                "Decime un nombre válido"
            )

        data["name"] = text

        # ✅ NUEVO: pasamos a confirmación antes del DONE
        return (
            ConversationState.ASK_CONFIRM,
            data,
            _build_summary(data)
        )

    # -------- ASK_CONFIRM (NUEVO) ----------
    if state == ConversationState.ASK_CONFIRM:
        yes = ["si", "sí", "dale", "ok", "oka", "confirmo", "confirmar", "de una", "listo"]
        no = ["no", "cancelar", "cancelo", "anular", "cambio", "modificar", "reiniciar"]

        if any(w == text or w in text for w in yes):
            return (
                ConversationState.DONE,
                data,
                "Perfecto ✅ Quedó confirmado. En breve te confirmo el total. 🙌"
            )

        if any(w == text or w in text for w in no):
            # reiniciamos pedido (simple y seguro)
            return (
                ConversationState.AWAITING_ORDER,
                {},
                "Dale, cancelamos y arrancamos de nuevo 😊 Decime tu pedido (ej: 2 hamburguesas y 1 coca)."
            )

        return (
            ConversationState.ASK_CONFIRM,
            data,
            "Decime **si** para confirmar o **no** para cancelar."
        )

    # -------- DONE ----------
    if state == ConversationState.DONE:
        # si el usuario escribe algo después, lo invitamos a pedir de nuevo
        return (
            ConversationState.NEW,
            {},
            "Si querés hacer otro pedido, escribime: hola 🙂"
        )

    # -------- FALLBACK ----------
    return (
        ConversationState.NEW,
        {},
        "Arranquemos de nuevo. Escribí hola."
    )
