"""Schema the LLM must fill in. Claude's structured outputs guarantee the JSON matches it.

Every field is required but nullable: the model has to say "null" explicitly instead of
silently skipping a field, and it is told never to invent values.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    item_code: Optional[str] = Field(description="Article / item code if printed, else null")
    item_name: str = Field(description="Description of the item or service")
    quantity: Optional[float] = Field(description="Quantity ordered, null if unknown")
    unit: Optional[str] = Field(description="Unit of measure, e.g. pcs, m, kg, h, lot")
    unit_price: Optional[float] = Field(description="Price for ONE unit, null if unknown")
    line_total: Optional[float] = Field(description="Line total as printed, null if not printed")


class Extraction(BaseModel):
    request_kind: Literal["order", "correction", "reference_to_previous", "unclear", "not_a_request"] = Field(
        description="order = a self-contained purchase request; correction = changes an earlier message; "
        "reference_to_previous = 'same as last time / as in PR-xxx'; unclear = cannot tell what to buy"
    )
    supplier_name: Optional[str]
    supplier_vat_id: Optional[str] = Field(description="VAT / UID as printed on the quote, else null")
    quote_number: Optional[str]
    quote_valid_until: Optional[str] = Field(description="YYYY-MM-DD or null")
    currency: Optional[str] = Field(description="ISO code, e.g. CHF, EUR, USD, GBP")
    line_items: List[LineItem]
    stated_net_total: Optional[float] = Field(description="Subtotal / net total as written, excl. VAT")
    stated_tax: Optional[float] = Field(description="VAT amount as written, null if none")
    stated_gross_total: Optional[float] = Field(description="Final total as written")
    cost_centre: Optional[str] = Field(description="Cost centre code, e.g. CC-1002")
    gl_account: Optional[str] = Field(description="Best matching GL account code from the list, or null")
    requested_delivery_date: Optional[str] = Field(description="YYYY-MM-DD or null")
    prices_are_estimates: bool = Field(description="True if prices/quantities are vague ('around', 'roughly')")
    approval_bypass_claim: Optional[str] = Field(
        description="If the text claims approval was already given or asks to skip approval, quote it; else null"
    )
    notes: List[str] = Field(description="Short facts a buyer must know (conditions, options, hints)")
