from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from cart.models import CartItem
from orders.models import Order
from orders.services import checkout
from shops.models import Product, Store

User = get_user_model()


class OrderAccessTests(TestCase):
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
        self.store = Store.objects.create(name="فروشگاه", owner=self.seller)
        self.product = Product.objects.create(
            name="محصول", price=Decimal("10000.00"), stock=5, store=self.store
        )
        CartItem.objects.create(customer=self.customer, product=self.product, quantity=2)
        self.order = checkout(
            customer_id=self.customer.pk, checkout_key=self.customer.checkout_key
        )

    def test_foreign_order_denied(self):
        other_user = User.objects.create_user(username="other", password="StrongPass!234")
        CustomerProfile.objects.create(user=other_user, phone="09120000001")

        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(reverse("orders:detail", args=[self.order.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("orders:thank_you", args=[self.order.pk])).status_code, 404
        )
        response = self.client.get(reverse("orders:history"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.order, response.context["orders"])

        self.client.force_login(self.customer_user)
        response = self.client.get(reverse("orders:history"))
        self.assertIn(self.order, response.context["orders"])

        # Sellers cannot use customer order pages.
        self.client.force_login(self.seller_user)
        self.assertEqual(self.client.get(reverse("orders:history")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("orders:checkout"), {"checkout_key": str(self.customer.checkout_key)}
            ).status_code,
            403,
        )

    def test_purchased_records_protected(self):
        with self.assertRaises(ProtectedError):
            self.product.delete()
        with self.assertRaises(ProtectedError):
            self.store.delete()

        self.product.refresh_from_db()
        self.store.refresh_from_db()
        self.assertEqual(Order.objects.count(), 1)
