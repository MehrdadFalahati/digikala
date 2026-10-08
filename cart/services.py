import uuid

from django.db import transaction

from accounts.models import CustomerProfile
from shops.models import Product

from .models import CartItem


class CartError(Exception):
    """Validation failure inside a cart service. Carries a stable code."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def _validated_quantity(quantity):
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise CartError("invalid_quantity", "تعداد باید عددی مثبت باشد.")
    return quantity


def _lock_customer(customer_id):
    # All cart mutations lock the customer profile first so that concurrent
    # mutations of one customer's cart are serialized.
    return CustomerProfile.objects.select_for_update().get(pk=customer_id)


def _rotate_checkout_key(customer):
    customer.checkout_key = uuid.uuid4()
    customer.save(update_fields=["checkout_key"])


@transaction.atomic
def add_item(*, customer_id: int, product_id: int, quantity: int) -> CartItem:
    """Add a product to the customer's cart, merging with an existing row."""
    quantity = _validated_quantity(quantity)
    customer = _lock_customer(customer_id)
    product = Product.objects.get(pk=product_id)

    item = CartItem.objects.filter(customer=customer, product=product).first()
    current_quantity = item.quantity if item else 0
    if current_quantity + quantity > product.stock:
        raise CartError("stock_exceeded", "تعداد درخواستی بیشتر از موجودی کالا است.")

    if item is None:
        item = CartItem.objects.create(customer=customer, product=product, quantity=quantity)
    else:
        item.quantity = current_quantity + quantity
        item.save(update_fields=["quantity"])

    _rotate_checkout_key(customer)
    return item


@transaction.atomic
def set_quantity(*, customer_id: int, item_id: int, quantity: int) -> CartItem:
    """Set the quantity of one of the customer's own cart rows."""
    quantity = _validated_quantity(quantity)
    customer = _lock_customer(customer_id)
    item = CartItem.objects.get(pk=item_id, customer=customer)

    if quantity > item.product.stock:
        raise CartError("stock_exceeded", "تعداد درخواستی بیشتر از موجودی کالا است.")

    item.quantity = quantity
    item.save(update_fields=["quantity"])
    _rotate_checkout_key(customer)
    return item


@transaction.atomic
def remove_item(*, customer_id: int, item_id: int) -> None:
    """Remove one of the customer's own cart rows."""
    customer = _lock_customer(customer_id)
    item = CartItem.objects.get(pk=item_id, customer=customer)
    item.delete()
    _rotate_checkout_key(customer)
