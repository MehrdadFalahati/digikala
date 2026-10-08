from decimal import Decimal

from django.db import transaction
from django.db.models import F

from .models import CustomerProfile

# Matches CustomerProfile.balance: DecimalField(max_digits=14, decimal_places=2).
MAX_BALANCE = Decimal("999999999999.99")


class WalletError(Exception):
    """Validation failure inside the wallet service. Carries a stable code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _validated_amount(amount):
    if not isinstance(amount, Decimal) or not amount.is_finite():
        raise WalletError("invalid_amount", "مبلغ وارد شده معتبر نیست.")
    if amount <= 0:
        raise WalletError("invalid_amount", "مبلغ باید عددی مثبت باشد.")
    if -amount.as_tuple().exponent > 2:
        raise WalletError("invalid_amount", "مبلغ می‌تواند حداکثر دو رقم اعشار داشته باشد.")
    if amount > MAX_BALANCE:
        raise WalletError("invalid_amount", "مبلغ از حد مجاز بیشتر است.")
    return amount


@transaction.atomic
def top_up(*, customer_id: int, amount: Decimal) -> Decimal:
    """Simulated wallet top-up. Returns the updated balance."""
    amount = _validated_amount(amount)
    customer = CustomerProfile.objects.select_for_update().get(pk=customer_id)
    if customer.balance + amount > MAX_BALANCE:
        raise WalletError("balance_overflow", "موجودی کیف پول از حد مجاز بیشتر می‌شود.")

    CustomerProfile.objects.filter(pk=customer.pk).update(balance=F("balance") + amount)
    customer.refresh_from_db()
    return customer.balance
