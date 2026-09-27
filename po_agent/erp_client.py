"""Client for the mock ERP (mock_po_api.py)."""
import requests

from .config import ERP_URL


def build_payload(req: dict) -> dict:
    ext, res = req["extraction"], req["result"]
    lines = []
    for line in ext["line_items"]:
        item = {
            "item_name": line["item_name"],
            "quantity": line["quantity"],
            "unit_price": line["unit_price"],
            "unit": line["unit"],
        }
        if line.get("item_code"):
            item["item_code"] = line["item_code"]
        lines.append(item)

    payload = {
        "supplier_id": res["supplier"]["id"],
        "currency": res["currency"],
        "total": res["net_total"],  # net amount; VAT is booked by the ERP
        "requested_delivery_date": res["delivery_date"],
        "cost_centre": res["cost_centre"],
        "requisition_reference": f"REQ-{req['id']:05d}",
        "line_items": lines,
    }
    if res.get("gl_account"):
        payload["gl_account"] = res["gl_account"]
    return payload


def create_purchase_order(req: dict) -> dict:
    """Returns {"ok": bool, "status_code": int, "body": dict}. Never raises."""
    payload = build_payload(req)
    # Same requisition -> same key, so a retry never books a second PO.
    headers = {"Idempotency-Key": f"req-{req['id']}-{req['message_id']}"}
    try:
        resp = requests.post(f"{ERP_URL}/purchase-orders", json=payload, headers=headers, timeout=10)
        body = resp.json()
    except requests.RequestException as err:
        return {"ok": False, "status_code": 0, "body": {"error": f"ERP not reachable: {err}"}, "payload": payload}
    except ValueError:
        body = {"error": resp.text}
    return {"ok": resp.status_code in (200, 201), "status_code": resp.status_code, "body": body, "payload": payload}


def health() -> dict:
    try:
        return requests.get(f"{ERP_URL}/health", timeout=3).json()
    except (requests.RequestException, ValueError):
        return {"status": "down"}


def list_orders() -> list:
    try:
        return requests.get(f"{ERP_URL}/purchase-orders", timeout=5).json()
    except (requests.RequestException, ValueError):
        return []
