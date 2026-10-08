from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import CustomerProfile
from shops.models import Product


class CartItem(models.Model):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="مشتری",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="محصول",
    )
    quantity = models.PositiveIntegerField(
        "تعداد",
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = "قلم سبد خرید"
        verbose_name_plural = "اقلام سبد خرید"
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "product"],
                name="unique_cart_item_per_customer",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="cart_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.customer} — {self.product} × {self.quantity}"

    @property
    def line_total(self):
        return self.product.price * self.quantity
