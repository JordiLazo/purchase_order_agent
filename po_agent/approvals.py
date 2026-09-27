"""Builds the approval chain. Pure functions, no LLM, fully unit-tested.

Rules from master_data.json:
- self_approval_forbidden: the requester never approves their own request. That step is
  escalated to the next role up (owner -> head -> finance -> CFO -> CEO).
- duplicate_role_collapses: if one person appears twice, they approve once.
- approvals_are_sequential: steps are approved in order.
"""
from typing import List, Optional

from .master_data import MasterData

ROLE_ORDER = ["cost_center_owner", "department_head", "finance", "cfo", "ceo"]


def required_roles(total_chf: float, md: MasterData) -> List[str]:
    for tier in md.approval_limits:  # tiers are sorted ascending
        if tier["to"] is None or total_chf <= tier["to"]:
            return list(tier["required_roles"])
    return list(md.approval_limits[-1]["required_roles"])


def approver_for_role(role: str, cost_centre: dict, md: MasterData) -> Optional[dict]:
    if role == "cost_center_owner":
        return md.employees.get(cost_centre["owner_employee_id"])
    if role == "department_head":
        dept = md.departments.get(cost_centre["department"])
        return md.employees.get(dept["head_employee_id"]) if dept else None
    people = [e for e in md.employees_with_role(role) if not e.get("deputy_for")]
    return people[0] if people else None


def deputies_of(employee_id: str, md: MasterData) -> List[dict]:
    return [e for e in md.employees.values() if e.get("deputy_for") == employee_id]


def build_chain(total_chf: float, cost_centre_code: str, requester_id: Optional[str], md: MasterData) -> List[dict]:
    cost_centre = md.cost_centres[cost_centre_code]
    chain: List[dict] = []

    for role in required_roles(total_chf, md):
        level = ROLE_ORDER.index(role)
        person = approver_for_role(role, cost_centre, md)
        note = ""

        # Self-approval forbidden: move up the hierarchy until someone else is found.
        while person and person["id"] == requester_id and level + 1 < len(ROLE_ORDER):
            level += 1
            person = approver_for_role(ROLE_ORDER[level], cost_centre, md)
            note = f"escalated from {role}: the requester cannot approve their own request"

        if person is None:
            chain.append({"role": role, "approver_id": None, "approver_name": "NOT FOUND",
                          "allowed_ids": [], "note": "no approver found in master data"})
            continue

        # Same person already in the chain: collapse into one approval.
        if any(step["approver_id"] == person["id"] for step in chain):
            continue

        allowed = [person["id"]] + [d["id"] for d in deputies_of(person["id"], md)]
        chain.append({
            "role": ROLE_ORDER[level],
            "approver_id": person["id"],
            "approver_name": person["name"],
            "allowed_ids": [a for a in allowed if a != requester_id],
            "note": note,
        })
    return chain
