from django.contrib import admin

from .models import Order, OrderItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Orders are financial history: view-only in the admin."""

    list_display = ("pk", "customer", "total_amount", "date")
    list_filter = ("date",)
    search_fields = ("customer__user__username",)
    readonly_fields = ("customer", "total_amount", "date", "checkout_key")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "product_name", "store", "quantity", "unit_price")
    search_fields = ("product_name",)
    readonly_fields = ("order", "product", "store", "product_name", "quantity", "unit_price")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
