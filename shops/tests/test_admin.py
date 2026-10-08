import queue
import threading
from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import OperationalError, connections, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from cart.models import CartItem
from orders.services import checkout
from shops.models import Product, Store

User = get_user_model()


class CatalogAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username="admin")
        seller = SellerProfile.objects.create(user=User.objects.create_user(username="seller"))
        self.customer = CustomerProfile.objects.create(
            user=User.objects.create_user(username="customer"),
            phone="09120000000",
            balance=Decimal("100000.00"),
        )
        self.store = Store.objects.create(name="فروشگاه", owner=seller)
        self.product = Product.objects.create(
            name="محصول", price=Decimal("10000.00"), stock=5, store=self.store
        )
        CartItem.objects.create(customer=self.customer, product=self.product, quantity=1)
        self.request = RequestFactory().post("/admin/")
        self.request.user = self.admin_user

    def test_store_admin_edit_preserves_checkout_credit(self):
        store_admin = admin.site._registry[Store]
        form_class = store_admin.get_form(self.request, obj=self.store)
        form = form_class(
            data={"name": "نام تازه", "description": "توضیح", "owner": self.store.owner_id},
            instance=self.store,
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = store_admin.save_form(self.request, form, change=True)

        checkout(customer_id=self.customer.pk, checkout_key=self.customer.checkout_key)
        store_admin.save_model(self.request, obj, form, change=True)

        self.store.refresh_from_db()
        self.assertEqual(self.store.balance, Decimal("10000.00"))
        self.assertEqual(self.store.name, "نام تازه")

    def test_product_admin_metadata_edit_preserves_sold_stock(self):
        product_admin = admin.site._registry[Product]
        form_class = product_admin.get_form(self.request, obj=self.product)
        initial_form = form_class(instance=self.product)
        version = {"stock_version": initial_form["stock_version"].value()}
        form = form_class(
            data={
                "name": "نام تازه", "description": "توضیح", "price": "10000.00",
                "stock": 5, "store": self.store.pk, "category": "",
                **version,
            },
            instance=self.product,
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = product_admin.save_form(self.request, form, change=True)

        checkout(customer_id=self.customer.pk, checkout_key=self.customer.checkout_key)
        product_admin.save_model(self.request, obj, form, change=True)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(self.product.name, "نام تازه")

    def test_product_admin_can_edit_stock(self):
        self.client.force_login(self.admin_user)
        url = reverse("admin:shops_product_change", args=[self.product.pk])
        initial_form = self.client.get(url).context["adminform"].form
        version = {"stock_version": initial_form["stock_version"].value()}
        response = self.client.post(
            url,
            {
                "name": "نام تازه", "description": "", "price": "12000.00",
                "stock": 8, "store": self.store.pk, "category": "", "_save": "Save",
                **version,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(self.product.price, Decimal("12000.00"))

    def test_product_admin_rejects_form_opened_before_checkout(self):
        self.client.force_login(self.admin_user)
        url = reverse("admin:shops_product_change", args=[self.product.pk])
        page = self.client.get(url)
        initial_form = page.context["adminform"].form
        payload = {
            "name": "نام تازه", "description": "", "price": "10000.00",
            "stock": 5, "store": self.store.pk, "category": "", "_save": "Save",
        }
        payload["stock_version"] = initial_form["stock_version"].value()

        checkout(customer_id=self.customer.pk, checkout_key=self.customer.checkout_key)
        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors.get("stock"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(self.product.name, "محصول")

    def test_product_admin_rejects_invalid_stock_version(self):
        self.client.force_login(self.admin_user)
        other_product = Product.objects.create(
            name="محصول دیگر", price=Decimal("10000.00"), stock=5, store=self.store
        )
        other_page = self.client.get(reverse("admin:shops_product_change", args=[other_product.pk]))
        other_form = other_page.context["adminform"].form
        other_version = other_form["stock_version"].value()
        for label, version in (("missing", ""), ("tampered", "tampered"), ("foreign", other_version)):
            with self.subTest(case=label):
                response = self.client.post(
                    reverse("admin:shops_product_change", args=[self.product.pk]),
                    {
                        "name": "نام تازه", "description": "", "price": "10000.00",
                        "stock": 8, "store": self.store.pk, "category": "",
                        "stock_version": version, "_save": "Save",
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors.get("stock_version"))
                self.product.refresh_from_db()
                self.assertEqual(self.product.stock, 5)

    def test_admin_can_create_product_without_stock_version(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("admin:shops_product_add"),
            {
                "name": "محصول تازه", "description": "", "price": "12000.00",
                "stock": 8, "store": self.store.pk, "category": "", "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name="محصول تازه")
        self.assertEqual(product.stock, 8)
        self.assertEqual(product.price, Decimal("12000.00"))


class ProductAdminConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username="admin")
        seller = SellerProfile.objects.create(user=User.objects.create_user(username="seller"))
        self.customer = CustomerProfile.objects.create(
            user=User.objects.create_user(username="customer"),
            phone="09120000000",
            balance=Decimal("100000.00"),
        )
        store = Store.objects.create(name="فروشگاه", owner=seller)
        self.product = Product.objects.create(
            name="محصول", price=Decimal("10000.00"), stock=5, store=store
        )
        CartItem.objects.create(customer=self.customer, product=self.product, quantity=1)

    def test_admin_product_edit_blocks_checkout_until_transaction_ends(self):
        request = RequestFactory().post("/admin/")
        request.user = self.admin_user
        product_admin = admin.site._registry[Product]
        results = queue.Queue()
        customer_id, key = self.customer.pk, self.customer.checkout_key

        def purchase():
            connections.close_all()
            try:
                with transaction.atomic():
                    with connections["default"].cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '500ms'")
                    order = checkout(customer_id=customer_id, checkout_key=key)
                    results.put(order.pk)
            except Exception as error:
                results.put(error)
            finally:
                connections.close_all()

        with transaction.atomic():
            obj = product_admin.get_object(request, str(self.product.pk))
            self.assertIsNotNone(obj)
            worker = threading.Thread(target=purchase, daemon=True)
            worker.start()
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive(), "checkout worker did not finish")
            result = results.get(timeout=1)
            self.assertIsInstance(result, OperationalError)
            self.assertEqual(result.__cause__.sqlstate, "55P03")

        order = checkout(customer_id=customer_id, checkout_key=key)
        self.assertEqual(order.total_amount, Decimal("10000.00"))
        self.product.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(self.customer.balance, Decimal("90000.00"))

    def test_admin_product_get_does_not_require_a_transaction(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin:shops_product_change", args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
