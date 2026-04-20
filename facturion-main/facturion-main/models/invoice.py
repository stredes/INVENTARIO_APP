from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Invoice:
    invoice_number: str
    invoice_date: str
    client: str
    description: str
    net_amount: float
    vat_rate: float
    vat_amount: float
    tag_amount: float
    accountant_amount: float
    savings_amount: float = 0.0
    total_amount: float = 0.0
    id: Optional[int] = None
