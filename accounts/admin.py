from django.contrib import admin

from .models import CustomerProfile, SellerProfile


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "balance")
    search_fields = ("user__username", "phone")
    readonly_fields = ("balance", "checkout_key")


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username",)
