from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, SellerProfile
from accounts.permissions import customer_for_user, seller_for_user

User = get_user_model()


class SignupTests(TestCase):
    def make_signup_payload(self, **overrides):
        payload = {
            "username": "newuser",
            "first_name": "کاربر",
            "last_name": "تازه",
            "phone": "09120000000",
            "role": "customer",
            "password1": "StrongPass!234",
            "password2": "StrongPass!234",
        }
        payload.update(overrides)
        return payload

    def test_customer_signup(self):
        response = self.client.post(reverse("accounts:signup"), self.make_signup_payload())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

        user = User.objects.get(username="newuser")
        self.assertTrue(user.check_password("StrongPass!234"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(SellerProfile.objects.filter(user=user).exists())

        customer = CustomerProfile.objects.get(user=user)
        self.assertEqual(customer.phone, "09120000000")
        self.assertEqual(customer.balance, Decimal("0.00"))
        self.assertEqual(customer_for_user(user), customer)
        self.assertIn("_auth_user_id", self.client.session)

    def test_seller_signup(self):
        payload = self.make_signup_payload(username="newshop", role="seller", phone="")
        response = self.client.post(reverse("accounts:signup"), payload)

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(username="newshop")
        self.assertTrue(SellerProfile.objects.filter(user=user).exists())
        self.assertFalse(CustomerProfile.objects.filter(user=user).exists())
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_invalid_signup(self):
        self.client.post(reverse("accounts:signup"), self.make_signup_payload())

        duplicate = self.client.post(
            reverse("accounts:signup"), self.make_signup_payload(phone="09120000001")
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.context["form"].errors.get("username"))
        self.assertEqual(User.objects.filter(username="newuser").count(), 1)

        mismatch = self.client.post(
            reverse("accounts:signup"),
            self.make_signup_payload(username="other", password2="Different!234"),
        )
        self.assertEqual(mismatch.status_code, 200)
        self.assertTrue(mismatch.context["form"].errors.get("password2"))

        bad_role = self.client.post(
            reverse("accounts:signup"), self.make_signup_payload(username="other2", role="admin")
        )
        self.assertEqual(bad_role.status_code, 200)
        self.assertTrue(bad_role.context["form"].errors.get("role"))

        no_phone = self.client.post(
            reverse("accounts:signup"), self.make_signup_payload(username="other3", phone="")
        )
        self.assertEqual(no_phone.status_code, 200)
        self.assertTrue(no_phone.context["form"].errors.get("phone"))

        self.assertFalse(
            User.objects.filter(username__in=["other", "other2", "other3"]).exists()
        )
        self.assertEqual(CustomerProfile.objects.count(), 1)
        self.assertEqual(SellerProfile.objects.count(), 0)

    def test_signup_cannot_grant_staff_access(self):
        payload = self.make_signup_payload(username="sneaky", is_staff="true", is_superuser="on")
        response = self.client.post(reverse("accounts:signup"), payload)

        self.assertEqual(response.status_code, 302)

        user = User.objects.get(username="sneaky")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)


class RoleGuardTests(TestCase):
    def setUp(self):
        self.customer_user = User.objects.create_user(username="cust", password="StrongPass!234")
        self.customer = CustomerProfile.objects.create(
            user=self.customer_user, phone="09120000000"
        )
        self.seller_user = User.objects.create_user(username="sell", password="StrongPass!234")
        self.seller = SellerProfile.objects.create(user=self.seller_user)

    def test_role_guards(self):
        self.assertEqual(customer_for_user(self.customer_user), self.customer)
        self.assertEqual(seller_for_user(self.seller_user), self.seller)

        with self.assertRaises(PermissionDenied):
            seller_for_user(self.customer_user)

        with self.assertRaises(PermissionDenied):
            customer_for_user(self.seller_user)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cust", password="StrongPass!234")

    def test_login_and_post_only_logout(self):
        bad = self.client.post(
            reverse("accounts:login"), {"username": "cust", "password": "wrong-password"}
        )
        self.assertEqual(bad.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

        good = self.client.post(
            reverse("accounts:login"), {"username": "cust", "password": "StrongPass!234"}
        )
        self.assertEqual(good.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)

        logged_out = self.client.post(reverse("accounts:logout"))
        self.assertEqual(logged_out.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
