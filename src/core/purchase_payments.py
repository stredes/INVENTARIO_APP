from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.data.models import Purchase, PurchasePayment
from src.utils.money import D, q2


PARTIAL_STATE = "Ingreso parcial"


def paid_amount(session: Session, purchase_id: int) -> Decimal:
    value = (
        session.query(func.coalesce(func.sum(PurchasePayment.monto), 0))
        .filter(PurchasePayment.id_compra == int(purchase_id))
        .scalar()
    )
    return q2(D(value or 0))


def debt_amount(session: Session, purchase: Purchase) -> Decimal:
    return q2(max(D(purchase.total_compra or 0) - paid_amount(session, int(purchase.id)), D(0)))


def refresh_purchase_payment_state(session: Session, purchase: Purchase) -> None:
    total = D(purchase.total_compra or 0)
    paid = paid_amount(session, int(purchase.id))
    if paid <= 0:
        if str(purchase.estado or "").strip() in (PARTIAL_STATE, "Completada"):
            purchase.estado = "Por pagar"
    elif paid < total:
        purchase.estado = PARTIAL_STATE
    else:
        purchase.estado = "Completada"


def add_purchase_payment(
    session: Session,
    purchase: Purchase,
    amount: Decimal,
    payment_date: datetime,
    note: str = "",
) -> PurchasePayment:
    amount = q2(D(amount))
    if amount <= 0:
        raise ValueError("El monto pagado debe ser mayor a 0.")
    current_debt = debt_amount(session, purchase)
    if amount > current_debt:
        raise ValueError(f"El pago supera la deuda pendiente ({current_debt}).")
    payment = PurchasePayment(
        id_compra=int(purchase.id),
        monto=amount,
        fecha_pago=payment_date,
        nota=note or None,
    )
    session.add(payment)
    session.flush()
    refresh_purchase_payment_state(session, purchase)
    return payment
