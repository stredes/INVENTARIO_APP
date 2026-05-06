from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from src.data.database import get_session
from src.data.models import Customer, SalesQuote, SalesQuoteDetail
from src.utils.money import D, q2, q0, money_sum


class SalesQuoteError(Exception):
    """Errores de logica de cotizaciones de venta."""


class SalesQuoteManager:
    """CRUD de cotizaciones de venta sin afectar inventario."""

    def __init__(self, session: Optional[Session] = None) -> None:
        self.session: Session = session or get_session()

    def _validate_customer(self, customer_id: int) -> None:
        exists = self.session.query(Customer.id).filter(Customer.id == customer_id).first()
        if not exists:
            raise SalesQuoteError(f"Cliente id={customer_id} no existe")

    @staticmethod
    def _line_subtotal(item: dict) -> Decimal:
        if item.get("subtotal") is not None:
            return q0(item.get("subtotal") or 0)
        qty = D(item.get("cantidad", 0) or 0)
        price = D(item.get("precio_eff", item.get("precio", 0)) or 0)
        disc = D(item.get("descuento_porcentaje", 0) or 0)
        return q0(qty * price * (D(1) - disc / D(100)))

    def _replace_details(self, quote: SalesQuote, items: Iterable[dict]) -> None:
        items = list(items)
        if not items:
            raise SalesQuoteError("La cotizacion debe contener al menos un item")

        quote.details.clear()
        total_lines: list[Decimal] = []
        for item in items:
            qty = int(float(item.get("cantidad", 0) or 0))
            if qty <= 0:
                raise SalesQuoteError("La cantidad debe ser mayor a 0")
            subtotal = self._line_subtotal(item)
            price = q0(item.get("precio_eff", item.get("precio", 0)) or 0)
            if price < 0 or subtotal < 0:
                raise SalesQuoteError("Los montos de la cotizacion no pueden ser negativos")

            kind = str(item.get("kind") or "product")
            product_id = item.get("id") if kind == "product" else None
            detail = SalesQuoteDetail(
                kind=kind,
                id_producto=int(product_id) if product_id else None,
                descripcion=str(item.get("nombre") or item.get("descripcion") or "").strip(),
                codigo=str(item.get("codigo") or "") or None,
                unidad=str(item.get("unidad") or "U") or "U",
                cantidad=qty,
                precio_unitario=price,
                descuento_porcentaje=q2(item.get("descuento_porcentaje", 0) or 0),
                subtotal=subtotal,
                afecto_iva=bool(item.get("afecto_iva", True)),
            )
            if not detail.descripcion:
                raise SalesQuoteError("La descripcion del item es obligatoria")
            quote.details.append(detail)
            total_lines.append(subtotal)
        quote.total = q0(money_sum(total_lines))

    def create_quote(
        self,
        *,
        customer_id: int,
        quote_number: str,
        items: Iterable[dict],
        notes: Optional[str] = None,
        payment: Optional[str] = None,
        currency: str = "CLP",
        price_includes_iva: bool = True,
    ) -> SalesQuote:
        self._validate_customer(customer_id)
        quote = SalesQuote(
            numero=str(quote_number).strip(),
            id_cliente=customer_id,
            fecha=datetime.utcnow(),
            total=D(0),
            estado="Abierta",
            forma_pago=payment,
            moneda=currency or "CLP",
            notas=notes,
            price_includes_iva=bool(price_includes_iva),
        )
        self.session.add(quote)
        self._replace_details(quote, items)
        self.session.commit()
        self.session.refresh(quote)
        return quote

    def update_quote(
        self,
        quote_id: int,
        *,
        customer_id: int,
        items: Iterable[dict],
        notes: Optional[str] = None,
        payment: Optional[str] = None,
        currency: str = "CLP",
        price_includes_iva: bool = True,
    ) -> SalesQuote:
        quote = self.session.get(SalesQuote, quote_id)
        if not quote:
            raise SalesQuoteError(f"Cotizacion id={quote_id} no existe")
        self._validate_customer(customer_id)
        quote.id_cliente = customer_id
        quote.forma_pago = payment
        quote.moneda = currency or "CLP"
        quote.notas = notes
        quote.price_includes_iva = bool(price_includes_iva)
        self._replace_details(quote, items)
        self.session.commit()
        self.session.refresh(quote)
        return quote

    def delete_quote(self, quote_id: int) -> None:
        quote = self.session.get(SalesQuote, quote_id)
        if not quote:
            return
        self.session.delete(quote)
        self.session.commit()

    def list_quotes(self) -> list[SalesQuote]:
        return (
            self.session.query(SalesQuote)
            .order_by(SalesQuote.id.desc())
            .all()
        )
