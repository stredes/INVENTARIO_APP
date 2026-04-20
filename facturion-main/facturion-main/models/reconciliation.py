from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Reconciliation:
    month: str
    sii_vat_amount: float
    actual_tag_paid: float = 0.0
    actual_accountant_paid: float = 0.0
    actual_savings_paid: float = 0.0
    observation: str = ""
    id: Optional[int] = None
