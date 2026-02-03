# app/services/state_machine.py
import re
from enum import Enum

# Intentamos importar IA (no rompe si no existe)
try:
    from app.services.llama_client import llama_extract, AI_ENABLED
except Exception:
    llama_extract = None
    AI_ENABLED = False


class ConversationState(str, Enum):
    NEW = "NEW"
    AWAITING_ORDER = "AWAITING_ORDER"
    ASK_DELIVERY = "ASK_DELIVERY"
    ASK_ADDRESS = "ASK_ADDRESS"
    ASK_PAYMENT = "ASK_PAYMENT"
    ASK_NAME = "ASK_NAME"
    ASK_CONFIRM = "ASK_CONFIRM"
    DONE = "DONE"


# ----------------------------
# Helpers de texto / menú
# ----------------------------

def _menu_intro_text() -> str:
    return (
        "Hola! Somos *Marietta* 👋\n"
        "📋 *Menú del día:*\n"
        f"{_read_menu_text_safe()}\n"
        "Decime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*)."
    )


def _read_menu_text_safe() -> str:
    # Si vos ya lo leés desde archivo en otro lado, podés reemplazar esto.
    # Mantengo un menú simple como el que venís usando.
    return (
        "📋 MENÚ MARIETTA (HOY)\n\n"
        "🍔 Hamburguesa simple $9000\n"
        "🍔 Hamburguesa doble $12000\n"
        "🍟 Papas $5000\n"
        "🍝 Tallarines $10000\n"
        "🥟 Empanadas de pollo $1500\n"
        "🥟 Empanadas de carne $1500\n"
        "🥤 Coca $2000\n"
    )


def _is_menu_request(text: str):
    t = (text or "").strip().lower()
    # preguntas típicas
    if any(k in t for k in ["menú", "menu", "carta", "tienen", "tenes", "tendran", "hay "]):
        # devolvemos el texto para contestar “sí/no” o “menú completo”
        return t
    return None


def _answer_menu_question(query: str) -> str:
    # respuesta ultra simple (la tuya ya andaba muy bien)
    menu = _read_menu_text_safe()
    q = (query or "").strip().lower()

    # si pregunta genérica, devolvemos menú
    if q in ["", "menu", "menú", "que tienen", "qué tienen", "carta"]:
        return "📋 *Menú del día:*\n" + menu + "\nDecime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*)."

    # si pregunta por un item puntual:
    # ejemplo: "tienen coca?"
    items = _menu_items_keywords()
    for it in items:
        if it in q:
            return f"Sí ✅ Hoy tenemos *{it}*.\n¿Querés pedir? Decime cantidades (ej: 2 hamburguesas y 1 coca)."

    # “fideos” => tallarines (sinónimos)
    if "fideos" in q:
        return "Sí ✅ Hoy tenemos *tallarines*.\n¿Querés pedir? Decime cantidades (ej: 2 hamburguesas y 1 coca)."

    return "📋 *Menú del día:*\n" + menu + "\nDecime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*)."


def _menu_items_keywords():
    # keywords base (minúsculas)
    return [
        "hamburguesa",
        "hamburguesa simple",
        "hamburguesa doble",
        "papas",
        "tallarines",
        "empanadas de pollo",
        "empanadas de carne",
        "coca",
    ]


# ----------------------------
# Parse regex (sin IA)
# ----------------------------

_NUM_WORDS = {
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15,
    "veinte": 20
}

def _word_to_int(token: str):
    token = (token or "").strip().lower()
    return _NUM_WORDS.get(token)


def _clean_item_name(name: str) -> str:
    n = (name or "").strip().lower()

    # normalizaciones mínimas
    n = n.replace("hamb", "hamburguesa")
    n = n.replace("hamburguesas", "hamburguesa")
    n = n.replace("cocas", "coca")

    # si dijo “hamburguesa doble” la dejamos así
    if "hamburguesa" in n and "doble" in n:
        return "hamburguesa doble"
    if "hamburguesa" in n and "simple" in n:
        return "hamburguesa simple"

    # si solo dijo hamburguesa
    if "hamburguesa" in n:
        return "hamburguesa"

    # papas
    if "papas" in n or "papa" in n:
        return "papas"

    # tallarines / fideos
    if "tallar" in n or "fideos" in n or "fideo" in n:
        return "tallarines"

    # empanadas
    if "empan" in n and "pollo" in n:
        return "empanadas de pollo"
    if "empan" in n and "carne" in n:
        return "empanadas de carne"
    if "empan" in n:
        return "empanadas"

    # coca
    if "coca" in n:
        return "coca"

    return n


def _parse_items_regex(text: str):
    """
    Devuelve lista items [{name, qty}] o [].
    IMPORTANTE: acá NO tocamos address, NI otros campos.
    """
    t = (text or "").strip().lower()
    if not t:
        return []

    # casos: "2 hamb + 1 coca"
    # o "quiero 12 hamburguesas"
    # o "quiero doce hamburguesas"
    items = []

    # reemplazos para facilitar
    t2 = t.replace("+", " ").replace(",", " ").replace("y", " ")

    # tokenizamos
    tokens = re.split(r"\s+", t2)

    # patrón: numero/palabra-numero + item
    # recorremos tokens buscando cantidades
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        qty = None

        if tok.isdigit():
            qty = int(tok)
        else:
            w = _word_to_int(tok)
            if w is not None:
                qty = w

        if qty is not None:
            # el nombre del item puede ocupar 1-3 tokens después
            name_parts = []
            for j in range(i + 1, min(i + 4, len(tokens))):
                if tokens[j].isdigit() or _word_to_int(tokens[j]) is not None:
                    break
                name_parts.append(tokens[j])

            name_raw = " ".join(name_parts).strip()
            name = _clean_item_name(name_raw)

            if name and name != "":
                items.append({"name": name, "qty": qty})
                i = i + 1 + len(name_parts)
                continue

        i += 1

    # fallback simple: si dijo “hamburguesa doble” sin número => no sirve para regex
    return items


# ----------------------------
# Parsers de otros datos
# ----------------------------

def _parse_delivery(text: str):
    t = (text or "").strip().lower()
    if any(k in t for k in ["envio", "envío", "enviar", "a domicilio", "delivery"]):
        return "envio"
    if any(k in t for k in ["retiro", "retirar", "lo paso a buscar", "busco", "paso a buscar"]):
        return "retiro"
    return None


def _parse_payment(text: str):
    t = (text or "").strip().lower()
    if "efectivo" in t:
        return "efectivo"
    if any(k in t for k in ["transfer", "transfe", "transferencia"]):
        return "transferencia"
    return None


def _looks_like_address(text: str) -> bool:
    t = (text or "").strip().lower()
    # heurística básica: calle + número
    return bool(re.search(r"[a-záéíóúñ]+\s+\d+", t))


def _extract_name(text: str):
    t = (text or "").strip()
    if not t:
        return None
    # "soy lucho" => "lucho"
    m = re.search(r"\bsoy\b\s+(.+)$", t, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t.strip()


# ----------------------------
# FUNCIÓN PRINCIPAL
# ----------------------------

def handle_message(state: str, text: str, data: dict):
    """
    OBLIGATORIO: devuelve EXACTAMENTE 3 valores:
      (next_state, new_data, reply_text)
    """
    if data is None:
        data = {}
    else:
        data = dict(data)  # copia defensiva

    state = (state or ConversationState.NEW).strip()

    # -------- NEW ----------
    if state == ConversationState.NEW or state == ConversationState.NEW.value:
        return (ConversationState.AWAITING_ORDER.value, data, _menu_intro_text())

    # -------- AWAITING_ORDER ----------
    if state == ConversationState.AWAITING_ORDER or state == ConversationState.AWAITING_ORDER.value:
        # 1) preguntas de menú
        q = _is_menu_request(text)
        if q is not None and any(k in q for k in ["menu", "menú", "carta", "tienen", "tenes", "hay", "hoy"]):
            return (ConversationState.AWAITING_ORDER.value, data, _answer_menu_question(q))

        # 2) intento regex
        items = _parse_items_regex(text)
        if items:
            data["items"] = items
            return (ConversationState.ASK_DELIVERY.value, data, "Genial 👍 ¿Es para retiro o envío?")

        # 3) fallback IA (opcional y seguro)
        if AI_ENABLED and llama_extract:
            ai = llama_extract(text)

            if isinstance(ai, dict) and ai.get("ok") is True:
                # items desde IA
                ai_items = ai.get("items") or []
                normalized = []
                for it in ai_items:
                    name = _clean_item_name(it.get("name", ""))
                    qty = it.get("qty", None)
                    if name:
                        # si qty viene vacío, lo forzamos a 1 para no trabar el flujo
                        if qty is None:
                            qty = 1
                        normalized.append({"name": name, "qty": qty})

                if normalized:
                    data["items"] = normalized
                    return (ConversationState.ASK_DELIVERY.value, data, "Genial 👍 ¿Es para retiro o envío?")

                # si la IA devolvió cosas sueltas, las guardamos SIN romper address
                for k in ["delivery_method", "payment_method", "name"]:
                    if ai.get(k):
                        data[k] = ai[k]

                # address solo si parece address real
                if ai.get("address") and _looks_like_address(ai["address"]):
                    data["address"] = ai["address"]

        return (
            ConversationState.AWAITING_ORDER.value,
            data,
            "No entendí 😕 Decime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*)."
        )

    # -------- ASK_DELIVERY ----------
    if state == ConversationState.ASK_DELIVERY or state == ConversationState.ASK_DELIVERY.value:
        dm = _parse_delivery(text)
        if not dm:
            return (ConversationState.ASK_DELIVERY.value, data, "Decime si es retiro o envío")
        data["delivery_method"] = dm
        if dm == "envio":
            return (ConversationState.ASK_ADDRESS.value, data, "Pasame tu dirección completa")
        else:
            # retiro: no pedimos address
            data.pop("address", None)
            return (ConversationState.ASK_PAYMENT.value, data, "¿Pagás en efectivo o transferencia?")

    # -------- ASK_ADDRESS ----------
    if state == ConversationState.ASK_ADDRESS or state == ConversationState.ASK_ADDRESS.value:
        # guardamos lo que venga (acá sí corresponde)
        data["address"] = (text or "").strip()
        return (ConversationState.ASK_PAYMENT.value, data, "¿Pagás en efectivo o transferencia?")

    # -------- ASK_PAYMENT ----------
    if state == ConversationState.ASK_PAYMENT or state == ConversationState.ASK_PAYMENT.value:
        pm = _parse_payment(text)
        if not pm:
            return (ConversationState.ASK_PAYMENT.value, data, "Efectivo o transferencia?")
        data["payment_method"] = pm
        return (ConversationState.ASK_NAME.value, data, "¿A nombre de quién preparo el pedido?")

    # -------- ASK_NAME ----------
    if state == ConversationState.ASK_NAME or state == ConversationState.ASK_NAME.value:
        name = _extract_name(text)
        if name:
            data["name"] = name.lower()
        return (ConversationState.ASK_CONFIRM.value, data, _build_confirm(data))

    # -------- ASK_CONFIRM ----------
    if state == ConversationState.ASK_CONFIRM or state == ConversationState.ASK_CONFIRM.value:
        t = (text or "").strip().lower()
        if t in ["si", "sí", "s", "ok", "dale", "confirmo", "confirmar"]:
            return (ConversationState.DONE.value, data, "Pedido confirmado ✅ En breve te confirmo el total.")
        if t in ["no", "n", "cancelar"]:
            return (ConversationState.NEW.value, {}, "Listo 👍 Si querés hacer otro pedido escribí *hola* 🙂")
        return (ConversationState.ASK_CONFIRM.value, data, "Respondé si o no")

    # -------- DONE ----------
    if state == ConversationState.DONE or state == ConversationState.DONE.value:
        return (ConversationState.NEW.value, {}, "Si querés hacer otro pedido escribí *hola* 🙂")

    # fallback
    return (ConversationState.NEW.value, {}, _menu_intro_text())


def _build_confirm(data: dict) -> str:
    items = data.get("items") or []
    lines = ["🧾 *Resumen del pedido*"]
    for it in items:
        qty = it.get("qty", 1)
        name = it.get("name", "")
        lines.append(f"- {qty} {name}")

    dm = data.get("delivery_method", "-")
    addr = data.get("address", "-") if dm == "envio" else "-"
    pm = data.get("payment_method", "-")
    nm = data.get("name", "-")

    lines.append("")
    lines.append(f"🚚 Modalidad: {dm}")
    lines.append(f"📍 Dirección: {addr}")
    lines.append(f"💳 Pago: {pm}")
    lines.append(f"🙋 Nombre: {nm}")
    lines.append("")
    lines.append("¿Confirmás? (si / no)")
    return "\n".join(lines)
