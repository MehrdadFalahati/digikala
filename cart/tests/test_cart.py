from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from cart.models import CartItem
from cart.services import CartError, add_item, set_quantity
from shops.models import Product, Store

User = get_user_model()


class CartTests(TestCase):
    def setUp(self):
        self.customer_user = User.objects.create_user(
            username="customer", password="StrongPass!234"
        )
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user, phone="09120000000"
        )
        self.seller_user = User.objects.create_user(
            username="seller", password="StrongPass!234"
        )
        self.seller = SellerProfile.objects.create(user=self.seller_user)
        self.store = Store.objects.create(name="فروشگاه یک", owner=self.seller)
        self.other_store = Store.objects.create(name="فروشگاه دو", owner=self.seller)
        self.product_a = Product.objects.create(
            name="محصول الف", price=Decimal("10000.00"), stock=5, store=self.store
        )
        self.product_b = Product.objects.create(
            name="محصول ب", price=Decimal("25000.00"), stock=4, store=self.other_store
        )

    def test_multistore_cart(self):
        self.client.force_login(self.customer_user)

        first = self.client.post(
            reverse("cart:add"), {"product_id": self.product_a.pk, "quantity": 2}
        )
        self.assertEqual(first.status_code, 302)
        second = self.client.post(
            reverse("cart:add"), {"product_id": self.product_b.pk, "quantity": 1}
        )
        self.assertEqual(second.status_code, 302)

        self.assertEqual(CartItem.objects.filter(customer=self.customer).count(), 2)

        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["total"],
            Decimal("10000.00") * 2 + Decimal("25000.00"),
        )

    def test_repeat_add_increments_quantity(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse("cart:add"), {"product_id": self.product_a.pk, "quantity": 2})
        self.client.post(reverse("cart:add"), {"product_id": self.product_a.pk, "quantity": 1})

        self.assertEqual(
            CartItem.objects.filter(customer=self.customer, product=self.product_a).count(), 1
        )
        item = CartItem.objects.get(customer=self.customer, product=self.product_a)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.line_total, self.product_a.price * Decimal(3))

    def test_invalid_quantities(self):
        with self.assertRaises(CartError) as raised:
            add_item(customer_id=self.customer.pk, product_id=self.product_a.pk, quantity=0)
        self.assertEqual(raised.exception.code, "invalid_quantity")

        with self.assertRaises(CartError):
            add_item(customer_id=self.customer.pk, product_id=self.product_a.pk, quantity=-2)

        with self.assertRaises(CartError) as raised:
            add_item(customer_id=self.customer.pk, product_id=self.product_a.pk, quantity=6)
        self.assertEqual(raised.exception.code, "stock_exceeded")

        self.assertFalse(CartItem.objects.filter(customer=self.customer).exists())

        add_item(customer_id=self.customer.pk, product_id=self.product_a.pk, quantity=4)
        with self.assertRaises(CartError):
            add_item(customer_id=self.customer.pk, product_id=self.product_a.pk, quantity=2)

        item = CartItem.objects.get(customer=self.customer, product=self.product_a)
        with self.assertRaises(CartError) as raised:
            set_quantity(customer_id=self.customer.pk, item_id=item.pk, quantity=6)
        self.assertEqual(raised.exception.code, "stock_exceeded")
        item.refresh_from_db()
        self.assertEqual(item.quantity, 4)

        # Invalid view input keeps the cart unchanged as well.
        self.client.force_login(self.customer_user)
        response = self.client.post(
            reverse("cart:add"), {"product_id": self.product_b.pk, "quantity": "abc"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CartItem.objects.filter(customer=self.customer, product=self.product_b).exists()
        )

        response = self.client.post(
            reverse("cart:add"), {"product_id": self.product_b.pk, "quantity": 99}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            CartItem.objects.filter(customer=self.customer, product=self.product_b).exists()
        )

    def test_foreign_cart_item_denied(self):
        other_user = User.objects.create_user(username="other", password="StrongPass!234")
        other_customer = CustomerProfile.objects.create(user=other_user, phone="09120000001")
        other_item = CartItem.objects.create(
            customer=other_customer, product=self.product_a, quantity=1
        )

        self.client.force_login(self.customer_user)
        response = self.client.post(reverse("cart:update", args=[other_item.pk]), {"quantity": 3})
        self.assertEqual(response.status_code, 404)

        response = self.client.post(reverse("cart:remove", args=[other_item.pk]))
        self.assertEqual(response.status_code, 404)

        other_item.refresh_from_db()
        self.assertEqual(other_item.quantity, 1)

        # Sellers are not customers and cannot use the cart.
        self.client.force_login(self.seller_user)
        self.assertEqual(self.client.get(reverse("cart:detail")).status_code, 403)

    def test_cart_mutation_rotates_checkout_key(self):
        self.client.force_login(self.customer_user)

        previous_checkout_key = self.customer.checkout_key
        self.client.post(reverse("cart:add"), {"product_id": self.product_a.pk, "quantity": 1})
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.checkout_key, previous_checkout_key)

        previous_checkout_key = self.customer.checkout_key
        item = CartItem.objects.get(customer=self.customer, product=self.product_a)
        self.client.post(reverse("cart:update", args=[item.pk]), {"quantity": 2})
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.checkout_key, previous_checkout_key)

        # A failed mutation must not rotate the key.
        previous_checkout_key = self.customer.checkout_key
        self.client.post(reverse("cart:update", args=[item.pk]), {"quantity": 0})
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.checkout_key, previous_checkout_key)

        self.client.post(reverse("cart:remove", args=[item.pk]))
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.checkout_key, previous_checkout_key)

    def test_cart_mutations_require_post(self):
        self.client.force_login(self.customer_user)
        item = CartItem.objects.create(
            customer=self.customer, product=self.product_a, quantity=1
        )

        self.assertEqual(self.client.get(reverse("cart:add")).status_code, 405)
        self.assertEqual(self.client.get(reverse("cart:update", args=[item.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse("cart:remove", args=[item.pk])).status_code, 405)

        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)
