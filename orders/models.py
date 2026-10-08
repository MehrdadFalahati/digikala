from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import CustomerProfile
from shops.models import Product, Store


class Order(models.Model):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="مشتری",
    )
    total_amount = models.DecimalField(
        "جمع کل (تومان)",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    date = models.DateTimeField("تاریخ ثبت", auto_now_add=True)
    checkout_key = models.UUIDField("کلید پرداخت", unique=True)

    class Meta:
        verbose_name = "سفارش"
        verbose_name_plural = "سفارش‌ها"
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"سفارش {self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="سفارش",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="محصول",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="فروشگاه",
    )
    # Purchase-time snapshots; product edits never change these values.
    product_name = models.CharField("نام محصول", max_length=200)
    quantity = models.PositiveIntegerField("تعداد", validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(
        "قیمت واحد (تومان)",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        verbose_name = "قلم سفارش"
        verbose_name_plural = "اقلام سفارش"

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
