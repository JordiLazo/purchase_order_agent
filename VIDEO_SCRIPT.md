# Video script: Purchase Order Agent

Three example emails for each possible outcome. No email is used in more than one case, except the Case 1
emails, which Cases 2 and 3 reuse on purpose. The AI extraction can vary slightly between runs, so do one
practice run before recording.

## Before recording

1. **Block two extra suppliers for Case 5.** In `master_data.json`, change `"status": "active"` to
   `"status": "blocked"` for **SUP-016 Alpine Logistics Services AG** and **SUP-022 IndustrieChemie Basel AG**.
   No other case uses these suppliers. Master data is loaded when the app starts, so do this before step 3.
   Change them back after recording.
2. **Terminal 1:** `cd purchase_order_agent && python3 mock_po_api.py 8080 data/orders.json`
3. **Terminal 2:** `cd purchase_order_agent && source .venv/bin/activate && streamlit run app.py`
4. In the app sidebar, click **Reset database**.
5. Check that the sidebar shows **ERP 🟢** and **LLM 🟢**.
6. Create the copies needed for Case 2 (same content, new Message-ID):
   ```bash
   sed 's/challenge-29-resend/challenge-29-copy/' email/email_29.eml > ~/Desktop/email_29_copy.eml
   sed 's/challenge-14@/challenge-14-copy@/'      email/email_14.eml > ~/Desktop/email_14_copy.eml
   sed 's/challenge-36@/challenge-36-copy@/'      email/email_36.eml > ~/Desktop/email_36_copy.eml
   ```
7. Don't show `.env` on screen, because it contains the API key.

**Intro (say):** "This agent turns purchase request emails into approved purchase orders in the ERP. The AI only
reads and extracts the data. Every business decision is plain code with fixed rules."

| # | Emails | Outcome |
|---|---|---|
| 1 | `email_29`, `email_14`, `email_36` | `PENDING_APPROVAL` → `PO_CREATED` |
| 2 | `email_29_copy`, `email_14_copy`, `email_36_copy` | `DUPLICATE` |
| 3 | `email_29`, `email_14`, `email_36` again | Existing requisition returned |
| 4 | `email_24`, `email_31`, `email_40` | `NEEDS_CLARIFICATION` |
| 5 | `email_09`, `email_34`, `email_42` | `REJECTED` (blocked supplier) |
| 6 | `email_16`, `email_11`, `email_43` | `REJECTED` (by an approver) |
| 7 | `email_03`, `email_33`, `email_05` | `ERP_ERROR` → `PO_CREATED` |
| 8 | `email_10`, `email_25`, `email_26` | `EXTRACTION_FAILED` → retry |

---

## Case 1: Happy path → `PENDING_APPROVAL` → `PO_CREATED`

| Email | Order | Total | Approval chain |
|---|---|---|---|
| `email_29.eml` | Hans Meier, Acme Bearings, PDF quote, CC-1002 | 1,751.40 EUR ≈ 1,681.34 CHF | Petra Brunner → Andrea Roth |
| `email_14.eml` | Miriam Frick, Elektro Bühler, CC-1002 | 1,001.00 CHF | Petra Brunner → Andrea Roth |
| `email_36.eml` | Miriam Frick, Global Fastener Supply, CC-1002 | 9,740 USD ≈ 8,571.20 CHF | Petra Brunner → Andrea Roth |

1. **Inbox** → select the three emails → **Process selected**.
2. **Requisitions** → open each one.
3. **Expected:** status ⏳ `PENDING_APPROVAL`, with the supplier, CHF total and approval chain from the table.
   For `email_29`, the line items come from the PDF.
4. For each requisition: acting as **Petra Brunner** → **Approve**. The next step becomes Andrea Roth.
5. Acting as **Andrea Roth** → **Approve**.
6. **Expected:** status `PO_CREATED` with a PO number.
7. Open **ERP orders**. The three new POs are listed there.

**Say:** "The amount is converted to CHF, and that decides who has to approve. 1,001 francs is just over the
1,000 limit, so it already needs the department head. Once the last person approves, the order goes to the ERP
automatically."

## Case 2: Same order sent again → `DUPLICATE`

**Emails:** `~/Desktop/email_29_copy.eml`, `email_14_copy.eml`, `email_36_copy.eml` (same orders, new Message-IDs)

1. **Inbox** → drag the three files in → **Process uploaded emails**.
2. **Expected:** each one has status `DUPLICATE`, with the message *"Duplicate of requisition #N - not ordered
   again."* Here #N is the matching requisition from Case 1.

**Say:** "Same supplier, cost centre and items, so the agent treats it as the same order and doesn't create a
second PO."

## Case 3: Same email processed twice → existing requisition returned

1. Upload `email/email_29.eml`, `email_14.eml` and `email_36.eml` again → **Process uploaded emails**.
2. **Expected:** for each one you get back the existing requisition from Case 1 instead of a new one, the AI
   isn't called again, and no new PO is created.

**Say:** "Every email has a unique ID, so processing it twice changes nothing."

## Case 4: Missing or inconsistent information → `NEEDS_CLARIFICATION`

| Email | Order | Blocking issue |
|---|---|---|
| `email_24.eml` | Kabelwerk quote | The sum of the lines doesn't match the stated total (4,380 vs 4,830, digits swapped) |
| `email_31.eml` | Nordic Tools quote | Quote NT-2026-0311 expired on 2026-04-30 |
| `email_40.eml` | Unknown cost centre | Cost centre CC-9100 does not exist |

1. Process the three emails and open each one.
2. **Expected:**
   - Status ❓ `NEEDS_CLARIFICATION`.
   - A yellow issue with the reason from the table.
   - A **Draft reply to requester** listing what needs fixing.

**Say:** "The agent never guesses. If something doesn't add up, it drafts a reply asking the requester."

## Case 5: Blocked supplier → `REJECTED`

| Email | Supplier |
|---|---|
| `email_09.eml` | SUP-018 Baltic Steel Trading OÜ (blocked in the original master data) |
| `email_34.eml` | SUP-022 IndustrieChemie Basel AG (blocked in step 1 of "Before recording") |
| `email_42.eml` | SUP-016 Alpine Logistics Services AG (blocked in step 1 of "Before recording") |

1. Process the three emails and open each one.
2. **Expected:** status ⛔ `REJECTED`, with a red issue saying the supplier is blocked in the master data.

**Say:** "Supplier status comes from the master data. If a supplier is blocked there, nothing gets ordered from
it."

## Case 6: An approver rejects → `REJECTED`

| Email | Order | First approver | Comment to type |
|---|---|---|---|
| `email_16.eml` | Tobias Weber, Bergmann tooling | Hans Meier | "Budget not available" |
| `email_11.eml` | Miriam Frick, Müller Industriebedarf | Daniel Kunz | "Please get a second quote" |
| `email_43.eml` | Sophie Dubois, Rapid Prototyping Studio | Fabio Rossi | "Project on hold" |

1. Process the three emails and open each one. The status is `PENDING_APPROVAL`.
2. Acting as the first approver → type the comment → **Reject**.
3. **Expected:** status `REJECTED`, and the audit log shows who rejected it and their comment.

## Case 7: ERP down → `ERP_ERROR` → retry → `PO_CREATED`

| Email | Order | Approval chain |
|---|---|---|
| `email_03.eml` | Lukas Frei, Nordic Tools, CC-2001 (his own cost centre) | Markus Schmid → Daniela Huber |
| `email_33.eml` | Tobias Weber, Hydraulik Zentrale | Hans Meier → Andrea Roth |
| `email_05.eml` | Sophie Dubois, SwissElectro | Anna Widmer → Markus Schmid |

1. Process the three emails and open each one.
2. **Expected for `email_03`:** the chain skips Lukas Frei, the cost centre owner, and starts with **Markus
   Schmid**, because nobody can approve their own request.
3. Stop the ERP: press **Ctrl+C in Terminal 1**.
4. For each requisition, approve every step in the chain from the table.
5. **Expected:** status `ERP_ERROR` with the message "ERP not reachable".
6. Restart the ERP with the command from step 2 of "Before recording". Then click **Send to ERP** on each
   requisition.
7. **Expected:** status `PO_CREATED`. Only one PO is created per requisition, because the retry reuses the same
   key.

## Case 8: AI call fails → `EXTRACTION_FAILED` → retry

**Emails:** `email_10.eml` (Werkstatt Huber, 480 CHF), `email_25.eml` (TechnoPlast), `email_26.eml`
(Verpackung Schneider)

1. Stop Streamlit (Ctrl+C in Terminal 2) and start it with a fake key. This doesn't touch `.env`:
   ```bash
   ANTHROPIC_API_KEY=invalid streamlit run app.py
   ```
2. Process the three emails.
3. **Expected:** each one has status `EXTRACTION_FAILED`, and the log says "Invalid or missing
   ANTHROPIC_API_KEY".
4. Stop Streamlit and start it normally with `streamlit run app.py`. Open each requisition → **Retry
   extraction**.
5. **Expected:** each email is processed normally and ends in `PENDING_APPROVAL`.

## Bonus: prompt injection in an email

**Email:** `email_50.eml` ("URGENT … the CFO already approved")

- **Expected:** status `PENDING_APPROVAL`, with a warning that the verbal approval was ignored. The full chain,
  including Finance and the CFO, still applies.

**Say:** "The email is treated as data, not as instructions. You can't skip approvals by writing that someone
already approved."

---

**Closing (say):** "There are 7 possible outcomes, and every decision is traceable in the audit log."

**After recording:** set SUP-016 and SUP-022 back to `"status": "active"` in `master_data.json`.
