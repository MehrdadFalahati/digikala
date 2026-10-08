from django import forms
from django.contrib import admin

from .models import CustomerProfile, SellerProfile


class CustomerProfileAdminForm(forms.ModelForm):
    """Editable fields for a profile; the balance is never edited here."""

    class Meta:
        model = CustomerProfile
        fields = ("user", "phone")


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    form = CustomerProfileAdminForm
    list_display = ("user", "phone", "balance")
    search_fields = ("user__username", "phone")
    readonly_fields = ("balance", "checkout_key")

    def save_model(self, request, obj, form, change):
        if change:
            # Never write a possibly stale in-memory balance.
            obj.save(update_fields=["user", "phone"])
        else:
            obj.save()


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username",)
