# Forward Deployed Engineer — Take-Home Challenge

This document covers the process: what you receive, how long you have, the rules you are working under, and how to submit. The problem itself was walked through with you in your interview.


## 1. What you receive

The download contains the input data and nothing else. There is no starter repository and no scaffolding.

| Item                | Count | Notes                                                |
| ------------------- | ----- | ---------------------------------------------------- |
| `emails/*.eml`      | 48    | Raw messages, as they arrived. Some carry attachments |
| `quotes/*.pdf`      | 21    | Supplier quotes and offers                           |
| `master_data.json`  | 1     | Suppliers, cost centres, departments, employees, GL accounts, FX rates |
| `mock_po_api.py`    | 1     | A stand-in purchase order endpoint. Standard library only |



## 2. Timeline and ground rules

### Timeline

| When                        | What happens                                                                 |
| --------------------------- | ---------------------------------------------------------------------------- |
| Day 0                       | You receive this document and the example input data.                        |
| 7 calendar days           | Roughly 4 hours of build time. Spread it however you want. We do not track hours. |
| After submission            | A 45-minute interview where you walk us through your solution.               |

If some questions come up underway, you can still ask via email.

### Ground rules

- Any programming language. We do not score the choice.
- Use of Claude Code, Cursor or similar AI coding tools is explicitly encouraged. We do this in our day-to-day.
- Use any libraries, frameworks or hosted services you want.
- You must understand every part of your solution. We will ask things like "why did you pick X over Y?", "what happens if the LLM returns garbage?", "how would you scale this to 500 requisitions a day?". "The AI wrote it" is not an acceptable answer.
- Document the assumptions you made wherever the spec was ambiguous. A short README is fine.
- Commit your work to a Git repository. GitHub, GitLab, or a zip with a `.git` folder are all fine.



## 3. Approval rules


Approval requirements are driven by the total value of the requisition in CHF.

| Total value (CHF) | Required approvers                                        |
| ----------------- | --------------------------------------------------------- |
| ≤ 1,000           | Cost Center Owner                                         |
| 1,001 – 10,000    | Cost Center Owner → Department Head                       |
| 10,001 – 50,000   | Cost Center Owner → Department Head → Finance              |
| 50,001 – 250,000  | Cost Center Owner → Department Head → Finance → CFO        |
| > 250,000         | Cost Center Owner → Department Head → Finance → CFO → CEO  |



## 4. What to submit

Three things:

1. **A Git repository** with your solution.
2. **A video walkthrough** of your solution. Loom, an unlisted YouTube link, or a file in the repository.
3. **A short README** in the repository covering how to run it and the assumptions you made where the spec was ambiguous.



## 5. The final interview

A remote final round, **1 hour in total**, split into two 30-minute sessions.

### Session 1 — Take-home review (30 min)

**Interviewer:** Sven Beck, CTO

| Minutes | What                                                                        |
| ------- | --------------------------------------------------------------------------- |
| 0 – 2   | You give us a one-minute summary.                                            |
| 2 – 10  | Live walkthrough. We will throw a new sample email at your running system and watch what happens. |
| 10 – 25 | Technical deep-dive. Expect "why this DB?", "what does your prompt look like?", "what happens if the PDF is 200 pages?", "how would you add a second customer?" |
| 25 – 30 | Your questions for us.                                                      |

Have your solution **running before the call starts**, on the machine you will share. We will give it an email it has not seen before.

### Session 2 — Role alignment (30 min)

**Interviewer:** Marc Felske, COO

Alignment on the role, your experience, and a Q&A-style conversation.