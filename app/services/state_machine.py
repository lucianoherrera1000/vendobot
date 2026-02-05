# app/services/state_machine.py
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Tuple


class ConversationState(str, Enum):
    NEW = "NEW"
    AWAITING_ORDER = "AWAITING_ORDER"
    ASK_DELIVERY = "ASK_DELIVERY"
    ASK_ADDRESS = "ASK_ADDRESS"
    ASK_PAYMENT = "ASK_PAYMENT"
    ASK_NAME = "ASK_NAME"
    ASK_CONFIRM = "ASK_CONFIRM"
    DONE = "DONE"


# ====== Config simple (podés moverlo a .env/archivo después) ======
DELIVERY_FEE = 3000

# Si tenés IA local integrada en llama_client.py, acá podés usarla sin romper nada:
# - Si no existe o falla, el bot sigue con regex.
try:
    from app.services.llama_client import llama_extract  # type: ignore
except Exception:
    llama_extract = None


# ====== Menú (mantenemos tu texto actual) ======
def _menu_text() -> str:
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


def _menu_intro_text() -> str:
    return (
        "Hola! Somos *Marietta* 👋\n"
        "📋 *Menú del día:*\n"
        f"{_menu_text()}\n"
        "Decime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*)."
    )


# ====== Helpers texto ======
_WORD_NUM = {
    "un": 1, "una": 1, "uno": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "dieciséis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20,
}

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _looks_like_menu_request(text: str) -> bool:
    t = _norm(text)
    if t in ("menu", "menú", "carta", "que tienen", "qué tienen", "que hay", "qué hay"):
        return True
    if "menu" in t or "menú" in t:
        return True
    if "que" in t and "tienen" in t:
        return True
    return False


def _is_greeting(text: str) -> bool:
    t = _norm(text)
    return any(x in t for x in ["hola", "buenas", "buen día", "buen dia", "buenas tardes", "buenas noches"])


def _parse_qty_token(tok: str) -> int | None:
    tok = _norm(tok)
    if tok.isdigit():
        try:
            return int(tok)
        except Exception:
            return None
    return _WORD_NUM.get(tok)


def _clean_item_name(name: str) -> str:
    n = _norm(name)
    n = n.replace("+", " ")
    n = re.sub(r"[^a-záéíóúüñ\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()

    # Normalizaciones típicas
    # (ajustá acá si querés mapping más estricto)
    if n in ("hamb", "hamburguesa", "hamburguesas"):
        return "hamburguesa"
    if "hamburguesa doble" in n:
        return "hamburguesa doble"
    if "hamburguesa simple" in n:
        return "hamburguesa simple"
    if "papa" in n or "papas" in n:
        return "papas"
    if "tallar" in n or "fideo" in n:
        return "tallarines"
    if "empanada" in n and "pollo" in n:
        return "empanadas de pollo"
    if "empanada" in n and "carne" in n:
        return "empanadas de carne"
    if "coca" in n:
        return "coca"

    return n


def _parse_items_regex(text: str) -> List[Dict[str, Any]]:
    """
    Soporta:
      - "2 hamburguesas y 1 coca"
      - "2 hamb + 1 coca"
      - "quiero 12 hamburguesas"
      - "quiero doce hamburguesas"
    """
    t = _norm(text)

    # atajo: "quiero 12 hamburguesas"
    m = re.search(r"\b(quiero|dame|mandame|mandáme)?\s*(\d+|[a-záéíóúüñ]+)\s+([a-záéíóúüñ\s]+)\b", t)
    # pero esto puede capturar basura; lo usamos solo si hay número/palabra-número clara
    items: List[Dict[str, Any]] = []

    # patrón clásico: "2 hamb", "1 coca", separados por y/+/, etc.
    parts = re.split(r"\s*(?:,| y |\+|\/)\s*", t)
    for p in parts:
        p = _norm(p)
        mm = re.match(r"^(?:(?:quiero|dame|mandame|mandáme)\s+)?(\d+|[a-záéíóúüñ]+)\s+(.+)$", p)
        if not mm:
            continue
        qty = _parse_qty_token(mm.group(1))
        if qty is None:
            continue
        name = _clean_item_name(mm.group(2))
        if not name:
            continue
        items.append({"name": name, "qty": qty})

    # si no detectó por parts, probamos captura simple "doce hamburguesas"
    if not items and m:
        qty = _parse_qty_token(m.group(2))
        if qty is not None:
            name = _clean_item_name(m.group(3))
            if name:
                items.append({"name": name, "qty": qty})

    return items


def _parse_delivery(text: str) -> str | None:
    t = _norm(text)
    if any(x in t for x in ["envio", "envío", "enviar", "delivery", "mandalo", "mandalo a casa", "a domicilio"]):
        return "envio"
    if any(x in t for x in ["retiro", "retira", "paso a buscar", "lo busco", "buscar", "retiro en local"]):
        return "retiro"
    return None


def _parse_payment(text: str) -> str | None:
    t = _norm(text)
    if "efectivo" in t:
        return "efectivo"
    if any(x in t for x in ["transfer", "transferencia", "tranfer", "trasnfer", "alias", "cbu", "mercadopago", "mp"]):
        return "transferencia"
    return None


def _parse_yes_no(text: str) -> bool | None:
    t = _norm(text)
    if t in ("si", "sí", "s", "dale", "ok", "oka", "confirmo", "confirmar", "confirmo si"):
        return True
    if t in ("no", "n", "cancelar", "cancelo"):
        return False
    return None


def _build_summary(data: Dict[str, Any]) -> str:
    items = data.get("items") or []
    lines = ["🧾 *Resumen del pedido*"]
    for it in items:
        lines.append(f"- {it.get('qty')} {it.get('name')}")
    lines.append("")
    dm = data.get("delivery_method") or "-"
    addr = data.get("address") if dm == "envio" else "-"
    pay = data.get("payment_method") or "-"
    nm = data.get("name") or "-"
    lines.append(f"🚚 Modalidad: {dm}")
    lines.append(f"📍 Dirección: {addr}")
    lines.append(f"💳 Pago: {pay}")
    lines.append(f"🙋 Nombre: {nm}")
    lines.append("")
    lines.append("¿Confirmás? (si / no)")
    return "\n".join(lines)


# ====== TOTAL (simple, basado en nombres normalizados) ======
_PRICE = {
    "hamburguesa": 9000,            # por defecto "hamburguesa" -> simple
    "hamburguesa simple": 9000,
    "hamburguesa doble": 12000,
    "papas": 5000,
    "tallarines": 10000,
    "empanadas de pollo": 1500,
    "empanadas de carne": 1500,
    "coca": 2000,
}

def _calc_total(data: Dict[str, Any]) -> int:
    total = 0
    for it in (data.get("items") or []):
        name = _clean_item_name(str(it.get("name", "")))
        qty = int(it.get("qty") or 0)
        price = _PRICE.get(name)
        if price is None:
            # fallback: si viene "hamburguesas" etc
            if "doble" in name and "hamb" in name:
                price = _PRICE["hamburguesa doble"]
            elif "hamb" in name:
                price = _PRICE["hamburguesa"]
            else:
                price = 0
        total += price * qty

    if data.get("delivery_method") == "envio":
        total += DELIVERY_FEE
    return total


# ====== Writer (usa tu servicio si existe) ======
try:
    from app.services.order_writer import write_order  # type: ignore
except Exception:
    write_order = None


def handle_message(
    state: str | None,
    text: str,
    data: Dict[str, Any] | None
) -> Tuple[str, Dict[str, Any], str]:
    """
    IMPORTANTE:
    - Debe devolver EXACTAMENTE 3 cosas (state, data, reply_text)
    - state es string (ConversationState.value)
    """
    if data is None:
        data = {}

    state_enum = ConversationState(state) if state in ConversationState._value2member_map_ else ConversationState.NEW
    next_state, new_data, reply = _step(state_enum, text, data)

    # garantizamos salida
    return (next_state.value, new_data, reply)


def _step(
    state: ConversationState,
    text: str,
    data: Dict[str, Any]
) -> Tuple[ConversationState, Dict[str, Any], str]:
    t = _norm(text)

    # -------- NEW ----------
    if state == ConversationState.NEW:
        return (ConversationState.AWAITING_ORDER, {}, _menu_intro_text())

    # -------- AWAITING_ORDER ----------
    if state == ConversationState.AWAITING_ORDER:
        # 1) Menú
        if _is_greeting(t) or _looks_like_menu_request(t):
            return (ConversationState.AWAITING_ORDER, data, _menu_intro_text() if _is_greeting(t) else _menu_intro_text().split("\n", 2)[1])

        # 2) Regex items
        items = _parse_items_regex(t)
        if items:
            data["items"] = items
            return (ConversationState.ASK_DELIVERY, data, "Genial 👍 ¿Es para retiro o envío?")

        # 3) Fallback IA (si está)
        if llama_extract:
            try:
                ai = llama_extract(text)  # tu llama_client puede armar prompt/JSON
                if isinstance(ai, dict) and ai.get("ok") is True:
                    ai_items = ai.get("items")
                    if ai_items:
                        normalized = []
                        for it in ai_items:
                            name = _clean_item_name(str(it.get("name", "")))
                            qty = it.get("qty", None)
                            if qty is None:
                                qty = 1
                            try:
                                qty = int(qty)
                            except Exception:
                                qty = 1
                            if name:
                                normalized.append({"name": name, "qty": qty})
                        if normalized:
                            data["items"] = normalized
                            return (ConversationState.ASK_DELIVERY, data, "Genial 👍 ¿Es para retiro o envío?")

                    # si IA detectó datos sueltos, los guardamos pero NO avanzamos de estado
                    for k in ["delivery_method", "address", "payment_method", "name"]:
                        if ai.get(k):
                            data[k] = ai[k]
                    return (ConversationState.AWAITING_ORDER, data, "Dale 🙂 decime tu pedido con cantidades (ej: 2 hamburguesas y 1 coca).")
            except Exception:
                pass

        return (ConversationState.AWAITING_ORDER, data, "No entendí 😕 Decime tu pedido con cantidades (ej: *2 hamburguesas y 1 coca*).")

    # -------- ASK_DELIVERY ----------
    if state == ConversationState.ASK_DELIVERY:
        dm = _parse_delivery(t)
        if dm:
            data["delivery_method"] = dm
            if dm == "envio":
                return (ConversationState.ASK_ADDRESS, data, "Pasame tu dirección completa")
            return (ConversationState.ASK_PAYMENT, data, "¿Pagás en efectivo o transferencia?")
        return (ConversationState.ASK_DELIVERY, data, "Decime si es retiro o envío")

    # -------- ASK_ADDRESS ----------
    if state == ConversationState.ASK_ADDRESS:
        # guardamos tal cual (si el cliente bardea, lo guarda… eso después lo filtramos)
        data["address"] = text.strip()
        return (ConversationState.ASK_PAYMENT, data, "¿Pagás en efectivo o transferencia?")

    # -------- ASK_PAYMENT ----------
    if state == ConversationState.ASK_PAYMENT:
        pm = _parse_payment(t)
        if pm:
            data["payment_method"] = pm
            return (ConversationState.ASK_NAME, data, "¿A nombre de quién preparo el pedido?")
        return (ConversationState.ASK_PAYMENT, data, "Efectivo o transferencia?")

    # -------- ASK_NAME ----------
    if state == ConversationState.ASK_NAME:
    # Guard rail: si el usuario manda "transferencia/efectivo" acá,
    # es que todavía estaba respondiendo el pago.
    pm = _parse_payment(t)
    if pm:
        data["payment_method"] = pm
        return (ConversationState.ASK_NAME, data, "Perfecto 👍 ¿A nombre de quién preparo el pedido?")

    # Otro guard rail: si te responde "envio/retiro" acá, es delivery atrasado
    dm = _parse_delivery(t)
    if dm:
        data["delivery_method"] = dm
        if dm == "envio":
            return (ConversationState.ASK_ADDRESS, data, "Dale 🙂 Pasame tu dirección completa")
        return (ConversationState.ASK_PAYMENT, data, "Buenísimo 🙂 ¿Pagás en efectivo o transferencia?")

    # Nombre normal
    name = re.sub(r"^\s*soy\s+", "", text.strip(), flags=re.IGNORECASE).strip()
    data["name"] = name if name else text.strip()
    return (ConversationState.ASK_CONFIRM, data, _build_summary(data))


    # -------- ASK_CONFIRM ----------
    if state == ConversationState.ASK_CONFIRM:
        yn = _parse_yes_no(t)
        if yn is None:
            return (ConversationState.ASK_CONFIRM, data, "Respondé si o no")
        if yn is False:
            return (ConversationState.DONE, {}, "Listo 👍 Si querés hacer otro pedido escribí *hola* 🙂")

        # Confirmado
        total = _calc_total(data)
        data["total"] = total

        # escribir orden si existe el writer
        if write_order:
            try:
                write_order(phone=data.get("phone", "unknown"), data=data)
            except Exception:
                # no rompemos el bot por fallo de escritura
                pass

        # mensaje final con total
        return (ConversationState.DONE, data, f"Pedido confirmado ✅ Total: ${total}. En breve te confirmo el tiempo de entrega.")

    # -------- DONE ----------
    if state == ConversationState.DONE:
        if _is_greeting(t):
            return (ConversationState.AWAITING_ORDER, {}, _menu_intro_text())
        return (ConversationState.DONE, data, "Si querés hacer otro pedido escribí *hola* 🙂")

    return (ConversationState.AWAITING_ORDER, data, _menu_intro_text())
