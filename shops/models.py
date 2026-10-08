from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from accounts.models import SellerProfile


class Store(models.Model):
    name = models.CharField("نام فروشگاه", max_length=100)
    description = models.TextField("توضیحات", blank=True)
    owner = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name="stores",
        verbose_name="مالک",
    )
    balance = models.DecimalField(
        "موجودی (تومان)",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        verbose_name = "فروشگاه"
        verbose_name_plural = "فروشگاه‌ها"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(balance__gte=0),
                name="store_balance_nonnegative",
            ),
        ]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField("نام", max_length=100, unique=True)
    slug = models.SlugField("شناسه", max_length=120, unique=True, allow_unicode=True)

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField("نام", max_length=200)
    description = models.TextField("توضیحات", blank=True)
    price = models.DecimalField(
        "قیمت (تومان)",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    stock = models.PositiveIntegerField("موجودی کالا", default=0)
    image = models.ImageField("تصویر", upload_to="products/", blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="دسته‌بندی",
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="products",
        verbose_name="فروشگاه",
    )
    created_at = models.DateTimeField("تاریخ ایجاد", auto_now_add=True)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصول‌ها"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.name
