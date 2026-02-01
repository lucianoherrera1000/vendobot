import re
import os
from datetime import datetime

from app.domain.states import ConversationState

# =========================================================
# AI (fallback)
# =========================================================
# Si todavía no creaste app/services/ai_client.py, NO rompe:
try:
    from app.services.ai_client import llama_extract
except Exception:
    llama_extract = None


# =========================================================
# CONFIG
# =========================================================
ORDERS_DIR = "orders"
MENU_FILE = "menu.txt"

if not os.path.exists(ORDERS_DIR):
    os.makedirs(ORDERS_DIR)


# =========================================================
# HELPERS: MENU
# =========================================================
def _read_menu_text_safe() -> str:
    try:
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _normalize_product_word(word: str) -> str:
    w = (word or "").lower().strip()
    # sinónimos básicos (podés extender cuando quieras)
    synonyms = {
        "fideos": "tallarines",
        "pasta": "tallarines",
        "coca cola": "coca",
        "cocacola": "coca",
        "hamb": "hamburguesa",
        "ham": "hamburguesa",
        "hambur": "hamburguesa",
        "hamburg": "hamburguesa",
    }
    return synonyms.get(w, w)


def _is_menu_request(text: str) -> str | None:
    """
    Detecta preguntas tipo:
      - "tienen coca?"
      - "hoy hay fideos?"
      - "menu?"
      - "que tienen?"
    Devuelve el producto consultado o None.
    """
    t = (text or "").lower().strip()

    # preguntas genéricas de menú
    if any(x in t for x in ["menu", "menú", "que tienen", "qué tienen", "carta", "lista"]):
        return ""  # significa "pedir menú completo"

    m = re.search(r"(tienen|hay|venden|sale)\s+([a-zA-Záéíóúñü ]+)\??$", t)
    if m:
        prod = m.group(2).strip()
        return _normalize_product_word(prod)

    # "hoy tienen fideos?" (más flexible)
    m2 = re.search(r"(hoy\s+)?(tienen|hay)\s+([a-zA-Záéíóúñü ]+)\??", t)
    if m2:
        prod = m2.group(3).strip()
        return _normalize_product_word(prod)

    return None


def _menu_intro_text() -> str:
    menu = _read_menu_text_safe()
    if not menu:
        return "Hola! Somos *Marietta* 👋\nHoy no pude cargar el menú todavía. Decime qué querés pedir 😊"
    return (
        "Hola! Somos *Marietta* 👋\n"
        "📋 *Menú del día:*\n"
        f"{menu}\n\n"
        "Decime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*)."
    )


def _answer_menu_question(query: str | None) -> str:
    menu = _read_menu_text_safe()

    # si no hay menu.txt
    if not menu:
        return "Hoy no tengo el menú cargado 😕 Decime qué querés y te digo si se puede."

    # si pidió menú completo
    if query is None or query == "":
        return (
            "📋 *Menú del día:*\n"
            f"{menu}\n\n"
            "Decime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*)."
        )

    q = _normalize_product_word(query)

    if q in menu.lower():
        return f"Sí ✅ Hoy tenemos *{q}*.\n¿Querés pedir? Decime cantidades (ej: 2 hamburguesas y 1 coca)."
    else:
        return (
            f"No 😕 Hoy no tenemos *{query}*.\n"
            "Podés pedir cualquiera de los items del menú 👇\n"
            f"{menu}\n\n"
            "Decime tu pedido con cantidades (ej: 2 hamburguesas y 1 coca)."
        )


# =========================================================
# HELPERS: ORDER SAVE + SUMMARY
# =========================================================
def _format_items(items):
    lines = []
    for it in items or []:
        qty = it.get("qty", 0)
        name = it.get("name", "")
        if name:
            # qty puede venir None si lo mandó IA sin cantidad
            if qty is None:
                lines.append(f"- {name} (sin cantidad)")
            else:
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


# =========================================================
# HELPERS: ORDER PARSER (REGEX)
# =========================================================
def _clean_item_name(s: str) -> str:
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

    # mini-normalizaciones
    s = _normalize_product_word(s)

    return s


def _parse_items_regex(text: str):
    """
    Acepta:
      - "2 hamburguesas y 1 coca"
      - "2 hamb + 1 coca"
    """
    items = []
    t = (text or "").lower().strip()

    matches = re.findall(r"(\d+)\s+([a-zA-ZáéíóúñüÁÉÍÓÚÑÜ ]+)", t)
    for qty, name in matches:
        name = _clean_item_name(name)
        if not name:
            continue
        items.append({"name": name, "qty": int(qty)})

    return items


# =========================================================
# MAIN FSM
# =========================================================
def handle_message(state, text, data):
    text = (text or "").lower().strip()

    # -------- NEW ----------
    if state == ConversationState.NEW:
        # si saluda/pide menú, mostramos menú directamente
        q = _is_menu_request(text)
        if q is not None:
            return (ConversationState.AWAITING_ORDER, {}, _menu_intro_text())

        # saludo simple
        if any(x in text for x in ["hola", "buenas", "buen día", "buen dia", "buenas tardes", "buenas noches"]):
            return (ConversationState.AWAITING_ORDER, {}, _menu_intro_text())

        # default
        return (ConversationState.AWAITING_ORDER, {}, _menu_intro_text())

    # -------- AWAITING_ORDER ----------
    if state == ConversationState.AWAITING_ORDER:
        # 1) Preguntas de menú (sin IA)
        q = _is_menu_request(text)
        if q is not None:
            # "" => menú completo
            return (ConversationState.AWAITING_ORDER, data, _answer_menu_question(q))

        # 2) Intento regex (sin IA)
        items = _parse_items_regex(text)
        if items:
            data["items"] = items
            return (ConversationState.ASK_DELIVERY, data, "Genial 👍 ¿Es para retiro o envío?")

        # 3) Fallback IA (solo si existe llama_extract)
        if llama_extract:
            menu_text = _read_menu_text_safe()
            ai = llama_extract(text, menu_text=menu_text)

            if isinstance(ai, dict):
                intent = (ai.get("intent") or "").strip().lower()

                # Si IA detecta pregunta menú
                if intent == "menu_question":
                    return (ConversationState.AWAITING_ORDER, data, _answer_menu_question(ai.get("menu_query")))

                # Si IA detecta saludo/presentación
                if intent == "greeting":
                    return (ConversationState.AWAITING_ORDER, data, _menu_intro_text())

                # Si IA detecta pedido sin cantidades o con info suelta
                if intent == "order":
                    ai_items = ai.get("items") or []
                    normalized = []
                    for it in ai_items:
                        name = _clean_item_name(it.get("name", ""))
                        qty = it.get("qty", None)
                        if name:
                            # qty puede ser None si no dijo cantidad
                            normalized.append({"name": name, "qty": qty})
                    if normalized:
                        data["items"] = normalized
                        return (ConversationState.ASK_DELIVERY, data, "Genial 👍 ¿Es para retiro o envío?")

        # Si no se pudo entender:
        return (
            ConversationState.AWAITING_ORDER,
            data,
            "No entendí 😕 Decime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*)."
        )

    # -------- ASK_DELIVERY ----------
    if state == ConversationState.ASK_DELIVERY:
        if any(w in text for w in ["envio", "envío", "a domicilio", "domicilio", "mandalo", "mandámelo"]):
            data["delivery_method"] = "envio"
        elif any(w in text for w in ["retiro", "retirar", "paso a buscar", "paso a buscarlo", "voy a buscar", "busco", "buscar", "paso"]):
            data["delivery_method"] = "retiro"
        else:
            return (ConversationState.ASK_DELIVERY, data, "¿Retiro o envío?")

        if data["delivery_method"] == "envio":
            return (ConversationState.ASK_ADDRESS, data, "Pasame tu dirección completa")

        return (ConversationState.ASK_PAYMENT, data, "¿Pagás en efectivo o transferencia?")

    # -------- ASK_ADDRESS ----------
    if state == ConversationState.ASK_ADDRESS:
        if len(text) < 5:
            return (
                ConversationState.ASK_ADDRESS,
                data,
                "Me pasás la dirección completa? (calle + número, y si hay dpto/barrio mejor)"
            )

        data["address"] = text
        return (ConversationState.ASK_PAYMENT, data, "¿Pagás en efectivo o transferencia?")

    # -------- ASK_PAYMENT ----------
    if state == ConversationState.ASK_PAYMENT:
        if "efectivo" in text:
            data["payment_method"] = "efectivo"
        elif any(w in text for w in ["transfer", "transf", "mercado pago", "mp", "alias", "cbu"]):
            data["payment_method"] = "transferencia"
        else:
            return (ConversationState.ASK_PAYMENT, data, "Efectivo o transferencia?")

        return (ConversationState.ASK_NAME, data, "¿A nombre de quién?")

    # -------- ASK_NAME ----------
    if state == ConversationState.ASK_NAME:
        # Si vuelve a decir "transferencia" acá, no lo tomamos como nombre
        if any(w in text for w in ["transfer", "transf", "mercado pago", "mp", "alias", "cbu"]):
            return (ConversationState.ASK_NAME, data, "Perfecto. Ahora decime tu nombre 🙂")

        if len(text) < 2:
            return (ConversationState.ASK_NAME, data, "Decime un nombre válido")

        data["name"] = text
        return (ConversationState.ASK_CONFIRM, data, _build_summary(data))

    # -------- ASK_CONFIRM ----------
    if state == ConversationState.ASK_CONFIRM:
        yes = ["si", "sí", "ok", "dale", "confirmo", "confirmar", "de una", "listo"]
        no = ["no", "cancelar", "cancelo", "anular", "cambio", "modificar", "reiniciar"]

        if any(w == text or w in text for w in yes):
            save_order_txt(data)
            return (ConversationState.DONE, data, "Pedido confirmado ✅ En breve te confirmo el total.")

        if any(w == text or w in text for w in no):
            return (ConversationState.AWAITING_ORDER, {}, "Perfecto, arrancamos de nuevo. ¿Qué querés pedir?")

        return (ConversationState.ASK_CONFIRM, data, "Respondé *si* o *no* 🙂")

    # -------- DONE ----------
    if state == ConversationState.DONE:
        return (ConversationState.NEW, {}, "Si querés hacer otro pedido escribí *hola* 🙂")

    # -------- FALLBACK ----------
    return (ConversationState.NEW, {}, "Escribí *hola* para empezar")
