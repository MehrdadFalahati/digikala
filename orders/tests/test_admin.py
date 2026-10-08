from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from cart.models import CartItem
from orders.models import Order, OrderItem
from orders.services import checkout
from shops.models import Product, Store

User = get_user_model()


class OrderAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username="admin")
        self.customer = CustomerProfile.objects.create(
            user=User.objects.create_user(username="customer"),
            phone="09120000000",
            balance=Decimal("100000.00"),
        )
        seller = SellerProfile.objects.create(user=User.objects.create_user(username="seller"))
        self.store = Store.objects.create(name="فروشگاه", owner=seller)
        self.product = Product.objects.create(
            name="محصول", price=Decimal("10000.00"), stock=5, store=self.store
        )
        CartItem.objects.create(customer=self.customer, product=self.product, quantity=1)
        self.order = checkout(customer_id=self.customer.pk, checkout_key=self.customer.checkout_key)
        self.item = self.order.items.get()
        self.client.force_login(self.admin_user)

    def assert_purchase_unchanged(self):
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())
        self.assertTrue(OrderItem.objects.filter(pk=self.item.pk).exists())
        self.customer.refresh_from_db()
        self.store.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("90000.00"))
        self.assertEqual(self.store.balance, Decimal("10000.00"))
        self.assertEqual(self.product.stock, 4)

    def test_admin_cannot_delete_order(self):
        response = self.client.post(
            reverse("admin:orders_order_delete", args=[self.order.pk]), {"post": "yes"}
        )
        self.assertEqual(response.status_code, 403)
        self.assert_purchase_unchanged()

    def test_admin_cannot_delete_order_item(self):
        response = self.client.post(
            reverse("admin:orders_orderitem_delete", args=[self.item.pk]), {"post": "yes"}
        )
        self.assertEqual(response.status_code, 403)
        self.assert_purchase_unchanged()

    def test_admin_bulk_delete_cannot_remove_order(self):
        self.client.post(
            reverse("admin:orders_order_changelist"),
            {"action": "delete_selected", "_selected_action": str(self.order.pk), "post": "yes"},
        )
        self.assert_purchase_unchanged()

    def test_admin_bulk_delete_cannot_remove_order_item(self):
        self.client.post(
            reverse("admin:orders_orderitem_changelist"),
            {"action": "delete_selected", "_selected_action": str(self.item.pk), "post": "yes"},
        )
        self.assert_purchase_unchanged()

    def test_admin_can_still_view_order_history(self):
        for model_name, pk in (("order", self.order.pk), ("orderitem", self.item.pk)):
            with self.subTest(model=model_name):
                response = self.client.get(reverse(f"admin:orders_{model_name}_change", args=[pk]))
                self.assertEqual(response.status_code, 200)
