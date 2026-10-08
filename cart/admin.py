from django.contrib import admin

from .models import CartItem


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("customer", "product", "quantity")
    search_fields = ("customer__user__username", "product__name")
