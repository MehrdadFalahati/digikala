import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class CustomerProfile(models.Model):
    """Wallet and cart owner attached to a Django user with the customer role."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
        verbose_name="کاربر",
    )
    phone = models.CharField("شماره تلفن", max_length=20)
    balance = models.DecimalField(
        "موجودی (تومان)",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    checkout_key = models.UUIDField("کلید پرداخت", default=uuid.uuid4, editable=False)

    class Meta:
        verbose_name = "پروفایل مشتری"
        verbose_name_plural = "پروفایل‌های مشتری"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=0),
                name="customer_balance_nonnegative",
            ),
        ]

    def __str__(self):
        return self.user.get_username()


class SellerProfile(models.Model):
    """Store owner attached to a Django user with the seller role."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seller_profile",
        verbose_name="کاربر",
    )

    class Meta:
        verbose_name = "پروفایل فروشنده"
        verbose_name_plural = "پروفایل‌های فروشنده"

    def __str__(self):
        return self.user.get_username()
