# app/services/order_writer.py
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict


def write_order(phone: str, data: Dict[str, Any], out_dir: str = "orders") -> str:
    """
    Guarda una orden en /orders con nombre timestamp_phone.txt
    Devuelve el path generado.
    """

    # root del proyecto (2 niveles arriba: app/services -> app -> project)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_path = os.path.join(base_dir, out_dir)
    os.makedirs(out_path, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_phone = "".join(c for c in (phone or "unknown") if c.isdigit() or c in ("+", "_", "-")) or "unknown"
    filename = f"{ts}_{safe_phone}.txt"
    fullpath = os.path.join(out_path, filename)

    items = data.get("items") or []
    lines = []
    lines.append(f"Fecha: {datetime.now().isoformat(sep=' ', timespec='seconds')}")
    lines.append(f"Telefono: {phone}")
    lines.append("")

    lines.append("Items:")
    for it in items:
        lines.append(f"- {it.get('qty')} {it.get('name')}")
    lines.append("")

    lines.append(f"Modalidad: {data.get('delivery_method')}")
    lines.append(f"Direccion: {data.get('address') if data.get('delivery_method') == 'envio' else '-'}")
    lines.append(f"Pago: {data.get('payment_method')}")
    lines.append(f"Nombre: {data.get('name')}")
    lines.append(f"Total: {data.get('total')}")
    lines.append("")

    with open(fullpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # opcional: último pedido por teléfono
    try:
        latest = os.path.join(out_path, f"latest_{safe_phone}.txt")
        with open(latest, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass

    return fullpath

