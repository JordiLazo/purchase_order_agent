# Purchase Order Agent

Turns **purchase request emails** (with or without a PDF quote) into **approved purchase orders registered in
the ERP**.

- **Video:** https://www.youtube.com/watch?v=7zSk-KI7BR8
- **GitHub repository:** https://github.com/JordiLazo/purchase_order_agent

```
.eml ─► Parsing ─► Extraction (Claude) ─► Validation ─► Approval chain ─► Approvals (UI) ─► ERP
```

The LLM **only extracts data**. All decisions (supplier, totals, approvers, rejections) are made by
deterministic Python code. Nothing unclear is guessed: the agent asks for clarification with a draft email.

## Structure

```
app.py            # Streamlit UI
cli.py            # Batch processing
mock_po_api.py    # Mock ERP
master_data.json  # Master data
email/  quotes/   # Sample emails and PDFs
po_agent/         # Parsing, extraction, validation, approvals, SQLite, ERP client
```

## Installation (macOS)

Requirements: Python 3.10+ and an Anthropic API key.

```bash
cd purchase_order_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your ANTHROPIC_API_KEY
mkdir -p data
```

## Running

**Terminal 1: mock ERP**
```bash
cd purchase_order_agent
python3 mock_po_api.py 8080 data/orders.json
```

**Terminal 2: UI**
```bash
cd purchase_order_agent
source .venv/bin/activate
streamlit run app.py        # http://localhost:8501
```

The sidebar should show **ERP 🟢** and **LLM 🟢**.

Without the UI:
```bash
source .venv/bin/activate
python3 cli.py --reset email/*.eml
```

## Usage

1. **Inbox**: upload `.eml` files or process the ones in `email/`.
2. **Requisitions**: status, issues, line items, approval chain, and a draft email if information is missing.
   Approve or reject as the approver of the current step.
3. When the last step is approved, the PO is sent to the ERP. **ERP orders** shows what was registered.

| Status | Meaning |
|---|---|
| `NEEDS_CLARIFICATION` | Information is missing or inconsistent |
| `REJECTED` | Blocked supplier, or rejected by an approver |
| `DUPLICATE` | The same order already exists |
| `PENDING_APPROVAL` | Waiting for the next approver |
| `PO_CREATED` | Registered in the ERP |
| `ERP_ERROR` / `EXTRACTION_FAILED` | Error; can be retried |

## Main rules

- Thresholds are in CHF on the **net** amount, using the exchange rates from the master data.
- No self-approval: if the requester would have to approve, the step moves up to the next role.
- If the same person appears twice in the chain, they approve only once.
- Approvals are sequential; Thomas Egger can stand in for Daniela Huber in Finance.
- The supplier is matched by VAT ID before name.
- Clarification is requested if prices, delivery date or cost centre are missing, if totals don't add up, or if
  the quote has expired.
- Verbal approvals ("the CFO already approved it") are ignored.
- Idempotency: the same `Message-ID` is never processed twice, and the PO is sent with an `Idempotency-Key`.
