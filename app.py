"""Streamlit UI.  Run with:  streamlit run app.py"""
import os

import pandas as pd
import streamlit as st

from po_agent import erp_client, storage
from po_agent.config import EMAIL_DIR, ERP_URL, MODEL
from po_agent.pipeline import clarification_email, current_step, decide, master_data, process_email, submit_to_erp

st.set_page_config(page_title="Purchase Order Agent", layout="wide")
md = master_data()

STATUS_ICON = {
    "PO_CREATED": "✅", "PENDING_APPROVAL": "⏳", "APPROVED": "👍", "NEEDS_CLARIFICATION": "❓",
    "REJECTED": "⛔", "DUPLICATE": "♊", "ERP_ERROR": "⚠️", "EXTRACTION_FAILED": "💥", "RECEIVED": "📩",
}

# ---------------------------------------------------------------- sidebar
st.sidebar.title("Purchase Order Agent")
page = st.sidebar.radio("Page", ["1 · Inbox", "2 · Requisitions", "3 · ERP orders"])

health = erp_client.health()
st.sidebar.markdown(f"**ERP** `{ERP_URL}`: {'🟢 up' if health.get('status') == 'ok' else '🔴 down'}")
st.sidebar.markdown(f"**LLM** `{MODEL}`: {'🟢 key set' if os.getenv('ANTHROPIC_API_KEY') else '🔴 no API key'}")
if st.sidebar.button("Reset database"):
    storage.reset(storage.connect())
    st.sidebar.success("Database cleared")


def run(files):
    """files: list of (name, bytes)."""
    bar = st.progress(0.0)
    for i, (name, raw) in enumerate(files, 1):
        bar.progress(i / len(files), text=f"Processing {name} ({i}/{len(files)})")
        req_id = process_email(raw, name)
        req = storage.get_requisition(storage.connect(), req_id)
        st.write(f"{STATUS_ICON.get(req['status'], '')} **{name}** → #{req_id} {req['status']}")
    bar.empty()


# ---------------------------------------------------------------- page 1: inbox
if page.startswith("1"):
    st.header("Inbox")
    st.caption("Upload new .eml files or process the sample emails in the email/ folder.")

    uploads = st.file_uploader("Upload .eml files", type=["eml"], accept_multiple_files=True)
    if uploads and st.button("Process uploaded emails", type="primary"):
        run([(u.name, u.getvalue()) for u in uploads])

    st.divider()
    files = sorted(p.name for p in EMAIL_DIR.glob("*.eml"))
    chosen = st.multiselect(f"Emails in {EMAIL_DIR.name}/ ({len(files)})", files)
    col1, col2 = st.columns(2)
    if col1.button("Process selected", disabled=not chosen):
        run([(n, (EMAIL_DIR / n).read_bytes()) for n in chosen])
    if col2.button(f"Process all {len(files)}"):
        run([(n, (EMAIL_DIR / n).read_bytes()) for n in files])

# ---------------------------------------------------------------- page 2: requisitions
elif page.startswith("2"):
    st.header("Requisitions")
    conn = storage.connect()
    reqs = storage.list_requisitions(conn)
    if not reqs:
        st.info("No requisitions yet. Process some emails on the Inbox page.")
        st.stop()

    rows = []
    for r in reqs:
        res = r["result"] or {}
        rows.append({
            "id": r["id"], "status": f"{STATUS_ICON.get(r['status'], '')} {r['status']}",
            "file": r["file_name"], "from": r["sender"],
            "supplier": (res.get("supplier") or {}).get("name"),
            "amount": f"{res['net_total']:,.2f} {res['currency']}" if res.get("net_total") is not None else "",
            "CHF": res.get("total_chf"), "PO": r["po_number"],
        })
    df = pd.DataFrame(rows)
    status_filter = st.multiselect("Filter by status", sorted({r["status"] for r in reqs}))
    if status_filter:
        df = df[df["status"].str.split(" ").str[-1].isin(status_filter)]
    st.dataframe(df, hide_index=True, width="stretch")

    req_id = st.selectbox("Open requisition", [r["id"] for r in reqs],
                          format_func=lambda i: f"#{i} - {next(r['file_name'] for r in reqs if r['id'] == i)}")
    req = storage.get_requisition(conn, req_id)
    res, ext = req["result"] or {}, req["extraction"] or {}

    st.subheader(f"#{req['id']} · {STATUS_ICON.get(req['status'], '')} {req['status']}")
    st.write(f"**From:** {req['sender']}  \n**Subject:** {req['subject']}")

    # Issues
    for issue in res.get("issues", []):
        {"reject": st.error, "block": st.warning, "warn": st.info}[issue["level"]](issue["message"])
    if req["duplicate_of"]:
        st.error(f"Duplicate of requisition #{req['duplicate_of']} - not ordered again.")

    # Key facts
    if res:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Supplier", (res.get("supplier") or {}).get("id") or "?", (res.get("supplier") or {}).get("name"),
                  delta_color="off")
        c2.metric("Net total", f"{res['net_total']:,.2f} {res['currency']}" if res.get("net_total") is not None else "?")
        c3.metric("Total CHF", f"{res['total_chf']:,.2f}" if res.get("total_chf") is not None else "?")
        c4.metric("Cost centre / delivery", res.get("cost_centre") or "?", res.get("delivery_date") or "no date",
                  delta_color="off")
    if ext.get("line_items"):
        st.dataframe(pd.DataFrame(ext["line_items"]), hide_index=True, width="stretch")

    # Approval chain
    if res.get("approval_chain"):
        st.markdown("#### Approval chain")
        approvals = storage.get_approvals(conn, req_id)
        if approvals:
            for a in approvals:
                icon = {"approved": "✅", "rejected": "⛔", "pending": "⏳"}[a["status"]]
                decided = f" by {md.employees[a['decided_by']]['name']}" if a["decided_by"] else ""
                st.write(f"{icon} Step {a['step_no']}: **{a['approver_name']}** ({a['role']}){decided} "
                         f"{'· _' + a['note'] + '_' if a['note'] else ''}")
        else:
            st.caption("Chain that would apply once the open points are resolved:")
            for i, s in enumerate(res["approval_chain"], 1):
                st.write(f"Step {i}: **{s['approver_name']}** ({s['role']}) {'· _' + s['note'] + '_' if s['note'] else ''}")

        step = current_step(approvals) if req["status"] == "PENDING_APPROVAL" else None
        if step:
            with st.form("approve"):
                st.write(f"**Current step {step['step_no']} – {step['role']}**")
                who = st.selectbox("Acting as", step["allowed_ids"], format_func=lambda i: md.employees[i]["name"])
                comment = st.text_input("Comment")
                a, b = st.columns(2)
                if a.form_submit_button("Approve", type="primary"):
                    st.success(decide(req_id, who, True, comment)); st.rerun()
                if b.form_submit_button("Reject"):
                    st.warning(decide(req_id, who, False, comment)); st.rerun()

    if req["status"] in ("APPROVED", "ERP_ERROR") and st.button("Send to ERP", type="primary"):
        st.info(submit_to_erp(req_id)); st.rerun()
    if req["status"] == "EXTRACTION_FAILED" and st.button("Retry extraction"):
        process_email(req["raw_email"], req["file_name"]); st.rerun()
    if req["status"] in ("NEEDS_CLARIFICATION", "REJECTED") and res.get("issues"):
        st.markdown("#### Draft reply to requester")
        st.text_area("Email", clarification_email(req), height=260)
    if req["erp_response"]:
        with st.expander("ERP response", expanded=req["status"] == "PO_CREATED"):
            st.json(req["erp_response"])

    with st.expander("Original email"):
        st.text(req["email_text"])
    with st.expander("LLM extraction (JSON)"):
        st.json(ext)
    with st.expander("Audit log"):
        for e in storage.get_events(conn, req_id):
            st.write(f"`{e['ts']}` {e['message']}")

# ---------------------------------------------------------------- page 3: ERP
else:
    st.header("Purchase orders in the ERP")
    orders = erp_client.list_orders()
    if not orders:
        st.info("No orders booked yet (or the ERP is not running).")
    for o in orders:
        with st.expander(f"{o['po_number']} · {o['supplier_id']} · {o['total']:,.2f} {o['currency']} · {o['cost_centre']}"):
            st.json(o)
