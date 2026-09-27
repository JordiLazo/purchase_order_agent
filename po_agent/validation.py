"""Deterministic business checks on top of the LLM extraction.

Each problem becomes an Issue with a level:
- "reject": the request cannot be ordered as is (e.g. blocked supplier)
- "block":  we need an answer from the requester before continuing
- "warn":   the buyer/approver should see it, but it does not stop the flow
"""
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import List, Optional

from .config import AMOUNT_TOLERANCE
from .email_reader import ParsedEmail
from .master_data import MasterData
from .models import Extraction


@dataclass
class Issue:
    level: str
    message: str


def parse_iso(value: Optional[str]) -> Optional[date]:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


def validate(ext: Extraction, email: ParsedEmail, md: MasterData) -> dict:
    issues: List[Issue] = []
    block = lambda m: issues.append(Issue("block", m))
    warn = lambda m: issues.append(Issue("warn", m))

    email_day = email.date.date() if email.date else date.today()

    # --- What kind of message is it -------------------------------------------------
    kinds = {
        "correction": "The email corrects an earlier message that is not available. Ask for the full request.",
        "reference_to_previous": "The email refers to a previous order/requisition that is not available. Ask for the details.",
        "unclear": "It is not clear what should be ordered. Ask the requester for supplier, items and quantities.",
        "not_a_request": "This email is not a purchase request.",
    }
    if ext.request_kind in kinds:
        block(kinds[ext.request_kind])

    # --- Requester ---------------------------------------------------------------
    requester = md.employee_by_email(email.sender_email)
    if requester is None:
        block(f"Sender {email.sender_email} is not a known employee.")

    # --- Supplier ----------------------------------------------------------------
    supplier, how = md.find_supplier(ext.supplier_name, ext.supplier_vat_id)
    if supplier is None:
        block(f"Supplier: {how}. A new supplier must be onboarded first.")
    else:
        if supplier["status"] != "active":
            issues.append(Issue("reject", f"Supplier {supplier['id']} {supplier['name']} is {supplier['status']}. "
                                          "Choose a different supplier."))
        if how != "matched by VAT id" and how != "matched by name":
            warn(f"Supplier {supplier['id']}: {how}.")

    # --- Line items and totals ----------------------------------------------------
    net_total = None
    if not ext.line_items:
        block("No line items found (attachment missing or no items listed).")
    else:
        complete = True
        for i, line in enumerate(ext.line_items, 1):
            missing = [f for f in ("quantity", "unit_price", "unit") if getattr(line, f) in (None, "")]
            if missing:
                complete = False
                block(f"Line {i} '{line.item_name}': missing {', '.join(missing)}.")
            elif line.line_total is not None and abs(line.quantity * line.unit_price - line.line_total) > AMOUNT_TOLERANCE:
                complete = False
                block(f"Line {i} '{line.item_name}': {line.quantity} x {line.unit_price} "
                      f"!= printed line total {line.line_total}.")
            elif line.unit_price == 0:
                warn(f"Line {i} '{line.item_name}' has price 0 (free of charge?).")
            elif line.unit_price < 0:
                warn(f"Line {i} '{line.item_name}' is a negative line (discount/credit).")
        if complete:
            net_total = round(sum(l.quantity * l.unit_price for l in ext.line_items), 2)

    if ext.prices_are_estimates:
        block("Prices or quantities are only estimates. A binding quote is needed.")

    if net_total is not None:
        stated = ext.stated_net_total
        if stated is None and ext.stated_gross_total is not None:
            stated = ext.stated_gross_total - (ext.stated_tax or 0)
        if stated is not None and abs(stated - net_total) > AMOUNT_TOLERANCE:
            block(f"Stated total {stated:,.2f} does not match the sum of the line items {net_total:,.2f}.")
        if ext.stated_gross_total is not None and ext.stated_net_total is not None:
            expected_gross = ext.stated_net_total + (ext.stated_tax or 0)
            if abs(expected_gross - ext.stated_gross_total) > AMOUNT_TOLERANCE:
                block(f"Quote arithmetic is wrong: net {ext.stated_net_total:,.2f} + tax "
                      f"{ext.stated_tax or 0:,.2f} != total {ext.stated_gross_total:,.2f}.")

    # --- Currency ----------------------------------------------------------------
    currency = (ext.currency or (supplier or {}).get("default_currency") or "").upper()
    if not ext.currency and currency:
        warn(f"No currency stated; using the supplier default {currency}.")
    total_chf = None
    if currency not in md.fx_rates:
        block(f"Currency '{currency or 'unknown'}' is not supported.")
    elif net_total is not None:
        total_chf = md.to_chf(net_total, currency)

    # --- Cost centre -------------------------------------------------------------
    cost_centre = ext.cost_centre
    if not cost_centre:
        block("No cost centre given.")
    elif cost_centre not in md.cost_centres:
        block(f"Cost centre {cost_centre} does not exist.")
        cost_centre = None
    elif requester and requester.get("default_cost_center") not in (None, cost_centre):
        owner = md.employees[md.cost_centres[cost_centre]["owner_employee_id"]]
        warn(f"Charged to {cost_centre}, not the requester's own cost centre. "
             f"{owner['name']} (owner) will approve.")

    gl_account = ext.gl_account if ext.gl_account in md.gl_accounts else None

    # --- Dates -------------------------------------------------------------------
    delivery = parse_iso(ext.requested_delivery_date)
    if delivery is None:
        block("No delivery date. The ERP needs a requested delivery date.")
    elif delivery < email_day:
        warn(f"Requested delivery date {delivery} is before the email date.")

    valid_until = parse_iso(ext.quote_valid_until)
    if valid_until and valid_until < email_day:
        block(f"Quote {ext.quote_number or ''} expired on {valid_until}. Ask for a fresh quote.")

    # --- Things a human should know ------------------------------------------------
    if ext.approval_bypass_claim:
        warn(f"Approval bypass requested and IGNORED - the standard approval chain applies: "
             f"\"{ext.approval_bypass_claim}\"")
    for att in email.attachments:
        if att.truncated:
            warn(f"Attachment {att.name} is very long; only the first pages were read. Check manually.")
    for note in ext.notes:
        warn(f"Note: {note}")

    return {
        "requester": requester,
        "supplier": supplier,
        "currency": currency or None,
        "net_total": net_total,
        "total_chf": total_chf,
        "cost_centre": cost_centre,
        "gl_account": gl_account,
        "delivery_date": delivery.isoformat() if delivery else None,
        "issues": [asdict(i) for i in issues],
    }
