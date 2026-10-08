import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase

from accounts.models import CustomerProfile, SellerProfile
from cart.models import CartItem
from orders.models import Order
from orders.services import CheckoutError, checkout
from shops.forms import StoreForm
from shops.models import Product, Store

User = get_user_model()


def run_concurrently(workers):
    """Run callables in threads with a start barrier and their own connections.

    The barrier ensures both workers reach the checkout call together; it is
    placed before any lock acquisition so the test itself cannot deadlock.
    """
    barrier = threading.Barrier(len(workers), timeout=10)
    results = [None] * len(workers)

    def runner(index, work):
        try:
            connections.close_all()
            barrier.wait()
            results[index] = work()
        except BaseException as exc:  # surfaced to the test for inspection
            results[index] = exc
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=runner, args=(index, work), daemon=True)
        for index, work in enumerate(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    if any(thread.is_alive() for thread in threads):
        raise AssertionError("a concurrent worker did not finish in time")
    return results


def assert_no_unexpected(results, allowed):
    for result in results:
        if not isinstance(result, allowed):
            raise result


class OversellConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.customer_one = self._make_customer("customer1", "09120000001")
        self.customer_two = self._make_customer("customer2", "09120000002")
        seller_user = User.objects.create_user(username="seller", password="StrongPass!234")
        seller = SellerProfile.objects.create(user=seller_user)
        self.store = Store.objects.create(name="فروشگاه", owner=seller)
        self.product = Product.objects.create(
            name="آخرین کالا", price=Decimal("10000.00"), stock=1, store=self.store
        )
        CartItem.objects.create(customer=self.customer_one, product=self.product, quantity=1)
        CartItem.objects.create(customer=self.customer_two, product=self.product, quantity=1)
        self.key_one = self.customer_one.checkout_key
        self.key_two = self.customer_two.checkout_key

    def _make_customer(self, username, phone):
        user = User.objects.create_user(username=username, password="StrongPass!234")
        return CustomerProfile.objects.create(
            user=user, phone=phone, balance=Decimal("100000.00")
        )

    def test_last_unit_not_oversold(self):
        customer_one, customer_two = self.customer_one, self.customer_two
        key_one, key_two = self.key_one, self.key_two
        results = run_concurrently(
            [
                lambda: checkout(customer_id=customer_one.pk, checkout_key=key_one),
                lambda: checkout(customer_id=customer_two.pk, checkout_key=key_two),
            ]
        )
        assert_no_unexpected(results, (Order, CheckoutError))

        orders = [result for result in results if isinstance(result, Order)]
        errors = [result for result in results if isinstance(result, CheckoutError)]
        self.assertEqual(len(orders), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, "insufficient_stock")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(Order.objects.count(), 1)
        self.customer_one.refresh_from_db()
        self.customer_two.refresh_from_db()
        self.assertEqual(
            self.customer_one.balance + self.customer_two.balance, Decimal("190000.00")
        )


class SameCustomerConcurrencyTests(TransactionTestCase):
    def setUp(self):
        user = User.objects.create_user(username="customer", password="StrongPass!234")
        self.customer = CustomerProfile.objects.create(
            user=user, phone="09120000000", balance=Decimal("100000.00")
        )
        seller_user = User.objects.create_user(username="seller", password="StrongPass!234")
        seller = SellerProfile.objects.create(user=seller_user)
        store = Store.objects.create(name="فروشگاه", owner=seller)
        product = Product.objects.create(
            name="محصول", price=Decimal("45000.00"), stock=3, store=store
        )
        CartItem.objects.create(customer=self.customer, product=product, quantity=1)
        self.key = self.customer.checkout_key

    def test_same_customer_charged_once(self):
        customer, key = self.customer, self.key
        results = run_concurrently(
            [
                lambda: checkout(customer_id=customer.pk, checkout_key=key),
                lambda: checkout(customer_id=customer.pk, checkout_key=key),
            ]
        )
        assert_no_unexpected(results, (Order, CheckoutError))

        orders = [result for result in results if isinstance(result, Order)]
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0].pk, orders[1].pk)

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("55000.00"))
        self.assertEqual(Order.objects.count(), 1)


class SharedStoreConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.customer_one = CustomerProfile.objects.create(
            user=User.objects.create_user(username="customer1", password="StrongPass!234"),
            phone="09120000001",
            balance=Decimal("100000.00"),
        )
        self.customer_two = CustomerProfile.objects.create(
            user=User.objects.create_user(username="customer2", password="StrongPass!234"),
            phone="09120000002",
            balance=Decimal("100000.00"),
        )
        seller_user = User.objects.create_user(username="seller", password="StrongPass!234")
        seller = SellerProfile.objects.create(user=seller_user)
        self.store = Store.objects.create(name="فروشگاه مشترک", owner=seller)
        self.product = Product.objects.create(
            name="محصول", price=Decimal("10000.00"), stock=2, store=self.store
        )
        CartItem.objects.create(customer=self.customer_one, product=self.product, quantity=1)
        CartItem.objects.create(customer=self.customer_two, product=self.product, quantity=1)
        self.key_one = self.customer_one.checkout_key
        self.key_two = self.customer_two.checkout_key

    def test_shared_store_credits_accumulate(self):
        customer_one, customer_two = self.customer_one, self.customer_two
        key_one, key_two = self.key_one, self.key_two
        results = run_concurrently(
            [
                lambda: checkout(customer_id=customer_one.pk, checkout_key=key_one),
                lambda: checkout(customer_id=customer_two.pk, checkout_key=key_two),
            ]
        )
        assert_no_unexpected(results, (Order, CheckoutError))

        orders = [result for result in results if isinstance(result, Order)]
        self.assertEqual(len(orders), 2)

        self.store.refresh_from_db()
        self.assertEqual(self.store.balance, Decimal("20000.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.customer_one.refresh_from_db()
        self.customer_two.refresh_from_db()
        self.assertEqual(self.customer_one.balance, Decimal("90000.00"))
        self.assertEqual(self.customer_two.balance, Decimal("90000.00"))


class StoreEditTests(TestCase):
    def setUp(self):
        self.customer_user = User.objects.create_user(
            username="customer", password="StrongPass!234"
        )
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user, phone="09120000000", balance=Decimal("100000.00")
        )
        seller_user = User.objects.create_user(username="seller", password="StrongPass!234")
        seller = SellerProfile.objects.create(user=seller_user)
        self.store = Store.objects.create(name="فروشگاه", owner=seller)
        product = Product.objects.create(
            name="محصول", price=Decimal("10000.00"), stock=5, store=self.store
        )
        CartItem.objects.create(customer=self.customer, product=product, quantity=2)

    def test_nonfinancial_store_edit_preserves_balance(self):
        # Load the edit form before the checkout credits the store.
        form = StoreForm(
            data={"name": "نام تازه", "description": "توضیح"}, instance=self.store
        )
        self.assertTrue(form.is_valid())

        checkout(customer_id=self.customer.pk, checkout_key=self.customer.checkout_key)

        form.save()

        self.store.refresh_from_db()
        self.assertEqual(self.store.balance, Decimal("20000.00"))
        self.assertEqual(self.store.name, "نام تازه")
