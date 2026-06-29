"""Billing module for the demo app.

Computes invoice totals with tax and applies simple coupon discounts.
Depends on :mod:`auth` only to attribute charges to a logged-in user.
"""

from auth import whoami

TAX_RATE = 0.20


def apply_coupon(amount: float, code: str) -> float:
    """Apply a known coupon code to ``amount`` and return the new subtotal."""
    discounts = {"WELCOME10": 0.10, "HACK50": 0.50}
    return amount * (1 - discounts.get(code, 0.0))


def invoice_total(amount: float, coupon: str | None = None) -> float:
    """Return the tax-inclusive total, optionally after a coupon discount."""
    subtotal = apply_coupon(amount, coupon) if coupon else amount
    return round(subtotal * (1 + TAX_RATE), 2)


def charge_user(token: str, amount: float, coupon: str | None = None) -> dict:
    """Charge the user behind ``token`` and return a receipt dict."""
    user = whoami(token)
    if user is None:
        raise PermissionError("invalid or expired token")
    return {"user": user, "total": invoice_total(amount, coupon)}
