import re
from dataclasses import dataclass

from app.domain.states import ConversationState


@dataclass
class StepResult:
    next_state: str
    reply_text: str
    data: dict


class StateMachine:
    def handle_message(self, state: str, text: str, data: dict) -> StepResult:
        data = data or {}
        text = (text or "").strip()
        t = text.lower()

        # 1) Inicio
        if state == ConversationState.NEW:
            return StepResult(
                next_state=ConversationState.GREETING,
                reply_text="Hola! Soy Vendobot 👋\n¿Querés hacer un pedido? Escribime lo que te gustaría comprar.",
                data=data,
            )

        # 2) Saludo -> pedir pedido
        if state == ConversationState.GREETING:
            return StepResult(
                next_state=ConversationState.AWAITING_ORDER,
                reply_text="Perfecto. Decime tu pedido (producto y cantidad). Ej: 2 hamburguesas y 1 coca",
                data=data,
            )

        # 3) Capturar items
        if state == ConversationState.AWAITING_ORDER:
            items = self.extract_items(text)
            if not items:
                return StepResult(
                    next_state=ConversationState.AWAITING_ORDER,
                    reply_text="No pude interpretar el pedido 😅. Probá: '2 hamburguesas y 1 coca'.",
                    data=data,
                )

            data["items"] = items
            return StepResult(
                next_state=ConversationState.ASK_DELIVERY,
                reply_text="Genial ✅ ¿Es para retiro o envío?",
                data=data,
            )

        # 4) Entrega (FASE 4)
        if state == ConversationState.ASK_DELIVERY:
            if "reti" in t:
                data["delivery_method"] = "retiro"
                return StepResult(
                    next_state=ConversationState.ASK_PAYMENT,
                    reply_text="Perfecto. ¿Pagás en efectivo o transferencia?",
                    data=data,
                )

            if "env" in t or "domi" in t:
                data["delivery_method"] = "envio"
                return StepResult(
                    next_state=ConversationState.ASK_ADDRESS,
                    reply_text="Dale 🙂 Pasame la dirección completa (calle, número, piso/depto y barrio).",
                    data=data,
                )

            return StepResult(
                next_state=ConversationState.ASK_DELIVERY,
                reply_text="Decime 'retiro' o 'envío', porfa 🙂",
                data=data,
            )

        # 4b) Dirección
        if state == ConversationState.ASK_ADDRESS:
            addr = text.strip()
            if len(addr) < 6:
                return StepResult(
                    next_state=ConversationState.ASK_ADDRESS,
                    reply_text="Me faltó la dirección 😅 Pasamela completa (calle y número).",
                    data=data,
                )

            data["address"] = addr
            return StepResult(
                next_state=ConversationState.ASK_PAYMENT,
                reply_text="Gracias ✅ ¿Pagás en efectivo o transferencia?",
                data=data,
            )

        # 5) Pago
        if state == ConversationState.ASK_PAYMENT:
            if "efec" in t:
                data["payment_method"] = "efectivo"
            elif "trans" in t:
                data["payment_method"] = "transferencia"
            else:
                return StepResult(
                    next_state=ConversationState.ASK_PAYMENT,
                    reply_text="Decime 'efectivo' o 'transferencia', porfa 🙂",
                    data=data,
                )

            # (Evolución) pedir nombre antes de cerrar
            return StepResult(
                next_state=ConversationState.ASK_NAME,
                reply_text="Genial ✅ ¿A nombre de quién lo preparo?",
                data=data,
            )

        # 6) Nombre
        if state == ConversationState.ASK_NAME:
            name = text.strip()
            if len(name) < 2:
                return StepResult(
                    next_state=ConversationState.ASK_NAME,
                    reply_text="Decime el nombre, porfa 🙂",
                    data=data,
                )

            data["name"] = name
            return StepResult(
                next_state=ConversationState.DONE,
                reply_text="Listo ✅ Tomé tu pedido. En breve te confirmo el total. ¿Algo más?",
                data=data,
            )

        # DONE: queda en modo espera
        if state == ConversationState.DONE:
            return StepResult(
                next_state=ConversationState.DONE,
                reply_text="Estoy acá 🙂 Si querés agregar algo, decime qué querés sumar al pedido.",
                data=data,
            )

        # Default
        return StepResult(
            next_state=state,
            reply_text="No entendí 😅 ¿podés repetir?",
            data=data,
        )

    def extract_items(self, text: str) -> list[dict]:
        """
        Muy simple (sin IA):
        - "2 hamburguesas y una coca" -> [{"name":"hamburguesas","qty":2},{"name":"coca","qty":1}]
        """
        if not text:
            return []

        # normalizar "una/un" => 1
        normalized = re.sub(r"\buna\b|\bun\b", "1", text.lower())
        parts = [p.strip() for p in normalized.split("y") if p.strip()]

        items = []
        for p in parts:
            m = re.match(r"^(\d+)\s+(.+)$", p)
            if m:
                qty = int(m.group(1))
                name = m.group(2).strip()
            else:
                qty = 1
                name = p.strip()

            name = re.sub(r"\s+", " ", name)
            if name:
                items.append({"name": name, "qty": qty})

        return items
