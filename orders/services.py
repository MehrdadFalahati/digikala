import uuid
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from accounts.models import CustomerProfile
from cart.models import CartItem
from shops.models import Product, Store

from .models import Order, OrderItem

# Matches the money fields: DecimalField(max_digits=14, decimal_places=2).
MAX_AMOUNT = Decimal("999999999999.99")


class CheckoutError(Exception):
    """Checkout failure with a stable code and a Persian message."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


@transaction.atomic
def checkout(*, customer_id: int, checkout_key) -> Order:
    """Run the simulated multi-store checkout atomically.

    Lock order: customer profile, products (ascending primary key), stores
    (ascending primary key).
    """
    if not isinstance(checkout_key, uuid.UUID):
        try:
            checkout_key = uuid.UUID(str(checkout_key))
        except (AttributeError, TypeError, ValueError):
            raise CheckoutError(
                "stale_checkout", "درخواست پرداخت نامعتبر است؛ صفحه را دوباره باز کنید."
            )

    customer = CustomerProfile.objects.select_for_update().get(pk=customer_id)

    # Idempotency: an already completed checkout for this customer/key returns
    # the same order without charging again.
    existing_order = Order.objects.filter(
        customer=customer, checkout_key=checkout_key
    ).first()
    if existing_order is not None:
        return existing_order

    # A key that does not match the profile means the cart changed after the
    # payment page was rendered.
    if customer.checkout_key != checkout_key:
        raise CheckoutError(
            "stale_checkout", "سبد خرید تغییر کرده است؛ صفحه را دوباره باز کنید."
        )

    cart_items = list(CartItem.objects.filter(customer=customer).select_related("product"))
    if not cart_items:
        raise CheckoutError("empty_cart", "سبد خرید شما خالی است.")

    product_ids = sorted({item.product_id for item in cart_items})
    locked_products = {
        product.pk: product
        for product in Product.objects.select_for_update()
        .filter(pk__in=product_ids)
        .order_by("pk")
    }

    # Re-read prices and stock from the locked rows; the browser total is
    # never trusted.
    total = Decimal("0.00")
    for item in cart_items:
        product = locked_products[item.product_id]
        if item.quantity > product.stock:
            raise CheckoutError(
                "insufficient_stock", f"موجودی کالای «{product.name}» کافی نیست."
            )
        total += product.price * item.quantity
    if total > MAX_AMOUNT:
        raise CheckoutError("amount_out_of_range", "مبلغ سفارش از حد مجاز بیشتر است.")

    store_shares = defaultdict(lambda: Decimal("0.00"))
    for item in cart_items:
        product = locked_products[item.product_id]
        store_shares[product.store_id] += product.price * item.quantity

    store_ids = sorted(store_shares)
    locked_stores = {
        store.pk: store
        for store in Store.objects.select_for_update()
        .filter(pk__in=store_ids)
        .order_by("pk")
    }
    for store_id, share in store_shares.items():
        if locked_stores[store_id].balance + share > MAX_AMOUNT:
            raise CheckoutError("amount_out_of_range", "مبلغ سفارش از حد مجاز بیشتر است.")

    if customer.balance < total:
        raise CheckoutError("insufficient_balance", "موجودی کیف پول برای این خرید کافی نیست.")

    updated = CustomerProfile.objects.filter(pk=customer.pk, balance__gte=total).update(
        balance=F("balance") - total
    )
    if updated != 1:
        raise CheckoutError("insufficient_balance", "موجودی کیف پول برای این خرید کافی نیست.")

    for store_id, share in store_shares.items():
        updated = Store.objects.filter(pk=store_id).update(balance=F("balance") + share)
        if updated != 1:
            raise RuntimeError("به‌روزرسانی موجودی فروشگاه ناموفق بود؛ عملیات برگردانده شد.")

    for item in cart_items:
        updated = Product.objects.filter(
            pk=item.product_id, stock__gte=item.quantity
        ).update(stock=F("stock") - item.quantity)
        if updated != 1:
            raise CheckoutError("insufficient_stock", "موجودی کالا کافی نیست.")

    order = Order.objects.create(
        customer=customer, total_amount=total, checkout_key=checkout_key
    )
    for item in cart_items:
        product = locked_products[item.product_id]
        OrderItem.objects.create(
            order=order,
            product=product,
            store_id=product.store_id,
            product_name=product.name,
            quantity=item.quantity,
            unit_price=product.price,
        )

    CartItem.objects.filter(customer=customer).delete()

    customer.checkout_key = uuid.uuid4()
    customer.save(update_fields=["checkout_key"])

    return order
