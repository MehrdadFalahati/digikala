from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from .models import CustomerProfile, SellerProfile


class SignupForm(UserCreationForm):
    """Registration with a customer or seller role and an atomic profile creation."""

    ROLE_CUSTOMER = "customer"
    ROLE_SELLER = "seller"

    first_name = forms.CharField(label="نام", max_length=150, required=False)
    last_name = forms.CharField(label="نام خانوادگی", max_length=150, required=False)
    phone = forms.CharField(label="شماره تلفن", max_length=20, required=False)
    role = forms.ChoiceField(
        label="نقش",
        choices=[
            (ROLE_CUSTOMER, "مشتری"),
            (ROLE_SELLER, "فروشنده"),
        ],
        widget=forms.RadioSelect,
    )

    class Meta(UserCreationForm.Meta):
        model = UserCreationForm.Meta.model
        fields = ("username", "first_name", "last_name")

    def clean(self):
        cleaned_data = super().clean()
        phone = (cleaned_data.get("phone") or "").strip()
        if cleaned_data.get("role") == self.ROLE_CUSTOMER and not phone:
            self.add_error("phone", "شماره تلفن برای مشتری الزامی است.")
        cleaned_data["phone"] = phone
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        # Registration can never grant staff or superuser access.
        user.is_staff = False
        user.is_superuser = False
        if not commit:
            return user
        with transaction.atomic():
            user.save()
            if self.cleaned_data["role"] == self.ROLE_SELLER:
                SellerProfile.objects.create(user=user)
            else:
                CustomerProfile.objects.create(user=user, phone=self.cleaned_data["phone"])
        return user


class TopUpForm(forms.Form):
    """Simulated wallet top-up. The money field maximum matches the model."""

    amount = forms.DecimalField(
        label="مبلغ (تومان)",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
