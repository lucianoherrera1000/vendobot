import os
from datetime import datetime


def save_order_txt(data: dict) -> str:
    """
    Guarda el pedido en /orders como .txt.
    Devuelve el path del archivo guardado.
    """
    os.makedirs("orders", exist_ok=True)

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    name = (data.get("name") or "cliente").strip().replace(" ", "_")
    filename = f"orders/{ts}_{name}.txt"

    items = data.get("items") or []
    delivery = data.get("delivery_method") or "-"
    address = data.get("address") or "-"
    payment = data.get("payment_method") or "-"

    lines = []
    lines.append(f"Nombre: {data.get('name', '-')}")
    lines.append("Items:")
    if items:
        for it in items:
            qty = it.get("qty", 0)
            nm = it.get("name", "")
            if nm:
                lines.append(f"- {qty} {nm}")
    else:
        lines.append("- (sin items)")

    lines.append(f"Modalidad: {delivery}")
    if delivery == "envio":
        lines.append(f"Direccion: {address}")
    lines.append(f"Pago: {payment}")

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return filename
