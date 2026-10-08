from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from accounts.services import WalletError, top_up

User = get_user_model()

STARTING_BALANCE = Decimal("100000.00")


class WalletTests(TestCase):
    def setUp(self):
        self.customer_user = User.objects.create_user(
            username="customer",
            first_name="مریم",
            last_name="احمدی",
            password="StrongPass!234",
        )
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user, phone="09120000000", balance=STARTING_BALANCE
        )

    def test_top_up_exact_amount(self):
        starting_balance = self.customer.balance
        result = top_up(customer_id=self.customer.pk, amount=Decimal("150000.00"))

        self.assertEqual(result, starting_balance + Decimal("150000.00"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, result)

        self.client.force_login(self.customer_user)
        response = self.client.post(reverse("accounts:payment"), {"amount": "50000.00"})
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, result + Decimal("50000.00"))

    def test_customer_panel(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse("accounts:customer_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "مریم")
        self.assertContains(response, "09120000000")
        self.assertContains(response, str(self.customer_user.pk))
        self.assertContains(response, "100000.00")
        self.assertContains(response, reverse("cart:detail"))
        self.assertContains(response, reverse("accounts:payment"))

        seller_user = User.objects.create_user(username="seller", password="StrongPass!234")
        SellerProfile.objects.create(user=seller_user)
        self.client.force_login(seller_user)
        self.assertEqual(self.client.get(reverse("accounts:customer_dashboard")).status_code, 403)

    def test_invalid_top_up_values(self):
        invalid_amounts = [
            Decimal("0"),
            Decimal("-5.00"),
            Decimal("NaN"),
            Decimal("Infinity"),
            Decimal("-Infinity"),
            Decimal("10.123"),
            Decimal("1000000000000000.00"),
        ]
        for amount in invalid_amounts:
            with self.assertRaises(WalletError):
                top_up(customer_id=self.customer.pk, amount=amount)
            self.customer.refresh_from_db()
            self.assertEqual(self.customer.balance, STARTING_BALANCE)

        # The view rejects the same inputs without changing balances.
        self.client.force_login(self.customer_user)
        for posted in ("0", "-5", "NaN", "Infinity", "10.123", "1000000000000000.00"):
            response = self.client.post(reverse("accounts:payment"), {"amount": posted})
            self.assertEqual(response.status_code, 200)
            self.customer.refresh_from_db()
            self.assertEqual(self.customer.balance, STARTING_BALANCE)

    def test_balance_overflow_rejected(self):
        self.customer.balance = Decimal("999999999999.00")
        self.customer.save(update_fields=["balance"])

        with self.assertRaises(WalletError) as raised:
            top_up(customer_id=self.customer.pk, amount=Decimal("1.00"))
        self.assertEqual(raised.exception.code, "balance_overflow")

        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("999999999999.00"))

        self.client.force_login(self.customer_user)
        response = self.client.post(reverse("accounts:payment"), {"amount": "1.00"})
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("999999999999.00"))

    def test_posted_customer_id_ignored(self):
        other_user = User.objects.create_user(username="other", password="StrongPass!234")
        other_customer = CustomerProfile.objects.create(
            user=other_user, phone="09120000001", balance=Decimal("50000.00")
        )

        self.client.force_login(self.customer_user)
        response = self.client.post(
            reverse("accounts:payment"),
            {"amount": "10000.00", "customer_id": str(other_customer.pk)},
        )
        self.assertEqual(response.status_code, 302)

        self.customer.refresh_from_db()
        other_customer.refresh_from_db()
        self.assertEqual(self.customer.balance, STARTING_BALANCE + Decimal("10000.00"))
        self.assertEqual(other_customer.balance, Decimal("50000.00"))
