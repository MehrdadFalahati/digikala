from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from cart.models import CartItem
from cart.services import add_item
from orders.models import Order, OrderItem
from orders.services import CheckoutError, checkout
from shops.models import Product, Store

User = get_user_model()


class CheckoutTests(TestCase):
    """Shared monetary fixture: balance 100000.00, A 10000.00 × 2, B 25000.00 × 1."""

    def setUp(self):
        self.customer_user = User.objects.create_user(
            username="customer", password="StrongPass!234"
        )
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user, phone="09120000000", balance=Decimal("100000.00")
        )
        self.seller_user = User.objects.create_user(
            username="seller", password="StrongPass!234"
        )
        self.seller = SellerProfile.objects.create(user=self.seller_user)
        self.store_a = Store.objects.create(name="فروشگاه الف", owner=self.seller)
        self.store_b = Store.objects.create(name="فروشگاه ب", owner=self.seller)
        self.product_a = Product.objects.create(
            name="محصول الف", price=Decimal("10000.00"), stock=5, store=self.store_a
        )
        self.product_b = Product.objects.create(
            name="محصول ب", price=Decimal("25000.00"), stock=4, store=self.store_b
        )
        CartItem.objects.create(customer=self.customer, product=self.product_a, quantity=2)
        CartItem.objects.create(customer=self.customer, product=self.product_b, quantity=1)

    def current_checkout_key(self):
        self.customer.refresh_from_db()
        return self.customer.checkout_key

    def test_multistore_checkout(self):
        order = checkout(customer_id=self.customer.pk, checkout_key=self.current_checkout_key())

        self.assertEqual(order.total_amount, Decimal("45000.00"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("55000.00"))
        self.store_a.refresh_from_db()
        self.assertEqual(self.store_a.balance, Decimal("20000.00"))
        self.store_b.refresh_from_db()
        self.assertEqual(self.store_b.balance, Decimal("25000.00"))
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.stock, 3)
        self.assertEqual(self.product_b.stock, 3)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.items.aggregate(total=Sum("quantity"))["total"], 3)
        self.assertFalse(CartItem.objects.filter(customer=self.customer).exists())

    def test_checkout_endpoint_flow(self):
        self.client.force_login(self.customer_user)
        key = self.current_checkout_key()

        response = self.client.post(reverse("orders:checkout"), {"checkout_key": str(key)})

        order = Order.objects.get(customer=self.customer)
        self.assertRedirects(response, reverse("orders:thank_you", args=[order.pk]))
        page = self.client.get(reverse("orders:thank_you", args=[order.pk]))
        self.assertContains(page, "45000.00")

    def test_checkout_requires_post(self):
        self.client.force_login(self.customer_user)
        self.assertEqual(self.client.get(reverse("orders:checkout")).status_code, 405)

    def test_checkout_replay(self):
        key = self.current_checkout_key()
        order = checkout(customer_id=self.customer.pk, checkout_key=key)

        replayed = checkout(customer_id=self.customer.pk, checkout_key=key)

        self.assertEqual(replayed.pk, order.pk)
        self.assertEqual(Order.objects.filter(customer=self.customer).count(), 1)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("55000.00"))
        self.store_a.refresh_from_db()
        self.assertEqual(self.store_a.balance, Decimal("20000.00"))
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock, 3)
        self.assertFalse(CartItem.objects.filter(customer=self.customer).exists())

    def test_stale_checkout_key(self):
        stale_key = self.current_checkout_key()
        # Any cart mutation rotates the profile key, invalidating the old one.
        add_item(customer_id=self.customer.pk, product_id=self.product_a.pk, quantity=1)

        with self.assertRaises(CheckoutError) as raised:
            checkout(customer_id=self.customer.pk, checkout_key=stale_key)
        self.assertEqual(raised.exception.code, "stale_checkout")

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("100000.00"))
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(customer=self.customer).count(), 2)

    def test_checkout_failures_preserve_state(self):
        key = self.current_checkout_key()

        CartItem.objects.all().delete()
        with self.assertRaises(CheckoutError) as raised:
            checkout(customer_id=self.customer.pk, checkout_key=key)
        self.assertEqual(raised.exception.code, "empty_cart")

        CartItem.objects.create(customer=self.customer, product=self.product_a, quantity=2)
        CartItem.objects.create(customer=self.customer, product=self.product_b, quantity=1)

        self.customer.balance = Decimal("100.00")
        self.customer.save(update_fields=["balance"])
        with self.assertRaises(CheckoutError) as raised:
            checkout(customer_id=self.customer.pk, checkout_key=key)
        self.assertEqual(raised.exception.code, "insufficient_balance")

        self.customer.balance = Decimal("100000.00")
        self.customer.save(update_fields=["balance"])
        self.product_a.stock = 1
        self.product_a.save(update_fields=["stock"])
        with self.assertRaises(CheckoutError) as raised:
            checkout(customer_id=self.customer.pk, checkout_key=key)
        self.assertEqual(raised.exception.code, "insufficient_stock")

        self.product_a.stock = 5
        self.product_a.price = Decimal("600000000000.00")
        self.product_a.save(update_fields=["stock", "price"])
        with self.assertRaises(CheckoutError) as raised:
            checkout(customer_id=self.customer.pk, checkout_key=key)
        self.assertEqual(raised.exception.code, "amount_out_of_range")

        self.product_a.price = Decimal("10000.00")
        self.product_a.save(update_fields=["price"])

        self.customer.refresh_from_db()
        self.store_a.refresh_from_db()
        self.store_b.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("100000.00"))
        self.assertEqual(self.store_a.balance, Decimal("0.00"))
        self.assertEqual(self.store_b.balance, Decimal("0.00"))
        self.assertEqual(self.product_a.stock, 5)
        self.assertEqual(self.product_b.stock, 4)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(customer=self.customer).count(), 2)

    def test_internal_failure_rolls_back(self):
        with mock.patch.object(
            OrderItem.objects, "create", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                checkout(customer_id=self.customer.pk, checkout_key=self.current_checkout_key())

        self.customer.refresh_from_db()
        self.store_a.refresh_from_db()
        self.store_b.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("100000.00"))
        self.assertEqual(self.store_a.balance, Decimal("0.00"))
        self.assertEqual(self.store_b.balance, Decimal("0.00"))
        self.assertEqual(self.product_a.stock, 5)
        self.assertEqual(self.product_b.stock, 4)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(customer=self.customer).count(), 2)

    def test_order_snapshots(self):
        order = checkout(customer_id=self.customer.pk, checkout_key=self.current_checkout_key())

        self.product_a.name = "نام تازه"
        self.product_a.price = Decimal("99999.00")
        self.product_a.save(update_fields=["name", "price"])

        item = order.items.get(product=self.product_a)
        self.assertEqual(item.product_name, "محصول الف")
        self.assertEqual(item.unit_price, Decimal("10000.00"))
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal("45000.00"))
