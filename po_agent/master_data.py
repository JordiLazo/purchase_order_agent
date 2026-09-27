"""Loads master_data.json and offers simple lookups."""
import difflib
import json
import re
from pathlib import Path
from typing import Optional, Tuple

from .config import MASTER_DATA_PATH

LEGAL_FORMS = {"gmbh", "ag", "kg", "ltd", "inc", "sa", "srl", "s", "r", "l", "bv", "as", "ou", "co", "oü"}


def normalize_name(name: str) -> str:
    name = name.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        name = name.replace(a, b)
    words = re.findall(r"[a-z0-9]+", name)
    return " ".join(w for w in words if w not in LEGAL_FORMS)


def normalize_vat(vat: str) -> str:
    vat = vat.upper().replace("MWST", "")
    return re.sub(r"[^A-Z0-9]", "", vat)


class MasterData:
    def __init__(self, path: Path = MASTER_DATA_PATH):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.fx_rates = data["_meta"]["fx_rates_to_chf"]
        self.suppliers = {s["id"]: s for s in data["suppliers"]}
        self.cost_centres = {c["code"]: c for c in data["cost_centers"]}
        self.departments = {d["code"]: d for d in data["departments"]}
        self.employees = {e["id"]: e for e in data["employees"]}
        self.gl_accounts = {g["code"]: g for g in data["gl_accounts"]}
        self.approval_limits = data["approval_limits_chf"]
        self.rules = data["rules"]

    def employee_by_email(self, email: str) -> Optional[dict]:
        email = (email or "").lower()
        return next((e for e in self.employees.values() if e["email"].lower() == email), None)

    def employees_with_role(self, role: str) -> list:
        return [e for e in self.employees.values() if e["role"] == role]

    def to_chf(self, amount: float, currency: str) -> Optional[float]:
        rate = self.fx_rates.get((currency or "").upper())
        return None if rate is None else round(amount * rate, 2)

    def find_supplier(self, name: Optional[str], vat: Optional[str]) -> Tuple[Optional[dict], str]:
        """Return (supplier, explanation). VAT id wins over name because names are ambiguous."""
        if vat:
            wanted = normalize_vat(vat)
            for s in self.suppliers.values():
                if s["vat_id"] and normalize_vat(s["vat_id"]) == wanted:
                    # Warn when the printed name belongs to a *different* supplier record.
                    if name and name.lower() != s["name"].lower():
                        others = [o for o in self.suppliers.values()
                                  if o["id"] != s["id"] and o["name"].lower() == name.lower()]
                        if others:
                            return s, (f"matched by VAT id, but the name '{name}' is supplier "
                                       f"{others[0]['id']} - please confirm")
                    return s, "matched by VAT id"

        if not name:
            return None, "no supplier name or VAT id found"

        wanted = normalize_name(name)
        by_name = {sid: normalize_name(s["name"]) for sid, s in self.suppliers.items()}

        exact = [sid for sid, n in by_name.items() if n == wanted]
        if len(exact) == 1:
            return self.suppliers[exact[0]], "matched by name"
        if len(exact) > 1:
            names = ", ".join(f"{sid} {self.suppliers[sid]['name']}" for sid in exact)
            return None, f"ambiguous: name matches several suppliers ({names})"

        close = difflib.get_close_matches(wanted, by_name.values(), n=2, cutoff=0.85)
        if len(close) == 1:
            sid = next(sid for sid, n in by_name.items() if n == close[0])
            return self.suppliers[sid], "fuzzy name match - please confirm"
        return None, f"supplier '{name}' not found in master data"
