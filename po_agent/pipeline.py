"""Orchestration: email -> extraction -> validation -> approval chain -> ERP.

Statuses:
  EXTRACTION_FAILED    the LLM call failed; can be retried
  NEEDS_CLARIFICATION  information is missing/inconsistent; a reply to the requester is drafted
  REJECTED             cannot be ordered (blocked supplier) or rejected by an approver
  DUPLICATE            same order already exists
  PENDING_APPROVAL     waiting for the next approver
  APPROVED             all approvals done (transient, immediately sent to the ERP)
  PO_CREATED           booked in the ERP
  ERP_ERROR            the ERP refused or was unreachable; can be retried
"""
import hashlib
import json

from . import erp_client, storage
from .approvals import build_chain
from .email_reader import email_as_text, parse_eml
from .extractor import ExtractionError, extract
from .master_data import MasterData
from .validation import validate

_md = None


def master_data() -> MasterData:
    global _md
    if _md is None:
        _md = MasterData()
    return _md


def fingerprint(result: dict, extraction: dict) -> str:
    """Same supplier + cost centre + items -> same order."""
    lines = sorted((l["item_name"].lower().strip(), l["quantity"], l["unit_price"]) for l in extraction["line_items"])
    key = json.dumps([result["supplier"]["id"] if result["supplier"] else None, result["cost_centre"], lines])
    return hashlib.sha256(key.encode()).hexdigest()


def decide_status(result: dict) -> str:
    levels = {i["level"] for i in result["issues"]}
    if "reject" in levels:
        return "REJECTED"
    if "block" in levels:
        return "NEEDS_CLARIFICATION"
    return "PENDING_APPROVAL"


def process_email(raw: bytes, file_name: str, extractor=extract) -> int:
    """Process one .eml file and return the requisition id. Safe to call twice for the same email."""
    md = master_data()
    email = parse_eml(raw)
    conn = storage.connect()

    existing = storage.find_by_message_id(conn, email.message_id)
    if existing and existing["status"] not in ("EXTRACTION_FAILED", "RECEIVED"):  # RECEIVED = crashed mid-run
        return existing["id"]  # idempotent: the same email is never processed twice
    if existing:
        req_id = existing["id"]
    else:
        req_id = storage.insert_requisition(
            conn, message_id=email.message_id, file_name=file_name,
            sender=f"{email.sender_name} <{email.sender_email}>", subject=email.subject,
            email_text=email_as_text(email), raw_email=raw, status="RECEIVED",
        )
        storage.log(conn, req_id, f"Email received: {file_name}")

    try:
        ext = extractor(email, md)
    except ExtractionError as err:
        storage.update_requisition(conn, req_id, status="EXTRACTION_FAILED")
        storage.log(conn, req_id, f"Extraction failed: {err}")
        return req_id

    extraction = ext.model_dump()
    result = validate(ext, email, md)

    # Approval chain is computed whenever the amount and cost centre are known,
    # so it is visible even if the request still needs clarification.
    chain = []
    if result["total_chf"] is not None and result["cost_centre"]:
        requester_id = result["requester"]["id"] if result["requester"] else None
        chain = build_chain(result["total_chf"], result["cost_centre"], requester_id, md)
    result["approval_chain"] = chain

    status = decide_status(result)
    fp = fingerprint(result, extraction) if extraction["line_items"] else None
    duplicate_of = None
    if fp and status != "REJECTED":
        dup = storage.find_by_fingerprint(conn, fp, exclude_id=req_id)
        if dup:
            status, duplicate_of = "DUPLICATE", dup["id"]

    storage.update_requisition(conn, req_id, status=status, extraction=extraction, result=result,
                               fingerprint=fp, duplicate_of=duplicate_of)
    storage.log(conn, req_id, f"Processed -> {status}" + (f" (duplicate of #{duplicate_of})" if duplicate_of else ""))
    if status == "PENDING_APPROVAL":
        storage.insert_approvals(conn, req_id, chain)
        storage.log(conn, req_id, "Approval chain: " + " -> ".join(f"{s['approver_name']} ({s['role']})" for s in chain))
    return req_id


def current_step(approvals: list):
    return next((a for a in approvals if a["status"] == "pending"), None)


def decide(req_id: int, approver_id: str, approve: bool, comment: str = "") -> str:
    """An approver approves/rejects the current step. Returns a message for the UI."""
    md = master_data()
    conn = storage.connect()
    req = storage.get_requisition(conn, req_id)
    if req["status"] != "PENDING_APPROVAL":
        return f"Requisition is {req['status']}, nothing to approve."

    step = current_step(storage.get_approvals(conn, req_id))
    if approver_id not in step["allowed_ids"]:
        return f"{approver_id} is not allowed to approve this step."

    name = md.employees[approver_id]["name"]
    storage.decide_approval(conn, step["id"], "approved" if approve else "rejected", approver_id, comment)
    storage.log(conn, req_id, f"Step {step['step_no']} ({step['role']}) {'approved' if approve else 'rejected'} by {name}. {comment}")

    if not approve:
        storage.update_requisition(conn, req_id, status="REJECTED")
        return "Requisition rejected."
    if current_step(storage.get_approvals(conn, req_id)) is None:
        storage.update_requisition(conn, req_id, status="APPROVED")
        storage.log(conn, req_id, "All approvals complete.")
        return submit_to_erp(req_id)
    return "Step approved. Waiting for the next approver."


def submit_to_erp(req_id: int) -> str:
    conn = storage.connect()
    req = storage.get_requisition(conn, req_id)
    if req["status"] not in ("APPROVED", "ERP_ERROR"):
        return f"Requisition is {req['status']}; only approved requisitions go to the ERP."
    resp = erp_client.create_purchase_order(req)
    if resp["ok"]:
        po = resp["body"]["po_number"]
        storage.update_requisition(conn, req_id, status="PO_CREATED", po_number=po, erp_response=resp)
        storage.log(conn, req_id, f"Purchase order {po} created in the ERP.")
        return f"Purchase order {po} created."
    storage.update_requisition(conn, req_id, status="ERP_ERROR", erp_response=resp)
    storage.log(conn, req_id, f"ERP error {resp['status_code']}: {resp['body']}")
    return f"ERP error: {resp['body']}"


def clarification_email(req: dict) -> str:
    """Draft reply to the requester listing what is missing."""
    res = req.get("result") or {}
    questions = [i["message"] for i in res.get("issues", []) if i["level"] in ("block", "reject")]
    name = (res.get("requester") or {}).get("name", "")
    bullet_list = "\n".join(f"- {q}" for q in questions)
    return (
        f"To: {req['sender']}\nSubject: Re: {req['subject']}\n\n"
        f"Hello {name.split(' ')[0] if name else ''},\n\n"
        f"thank you for your purchase request. Before we can order, we need the following:\n\n"
        f"{bullet_list}\n\nPlease reply to this email with the missing information.\n\n"
        f"Best regards,\nProcurement"
    )
