from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import customer_for_user
from shops.models import Product

from .forms import AddToCartForm, UpdateCartItemForm
from .models import CartItem
from .services import CartError, add_item, remove_item, set_quantity


@login_required
def detail(request):
    customer = customer_for_user(request.user)
    items = CartItem.objects.filter(customer=customer).select_related(
        "product", "product__store"
    )
    total = sum((item.line_total for item in items), Decimal("0.00"))
    return render(request, "cart.html", {"items": items, "total": total, "customer": customer})


@login_required
@require_POST
def add(request):
    customer = customer_for_user(request.user)
    form = AddToCartForm(request.POST)
    if not form.is_valid():
        messages.error(request, "تعداد وارد شده نامعتبر است.")
        return redirect("cart:detail")

    product = get_object_or_404(Product, pk=form.cleaned_data["product_id"])
    try:
        add_item(
            customer_id=customer.pk,
            product_id=product.pk,
            quantity=form.cleaned_data["quantity"],
        )
    except CartError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, "محصول به سبد خرید افزوده شد.")
    return redirect("cart:detail")


@login_required
@require_POST
def update(request, item_id):
    customer = customer_for_user(request.user)
    form = UpdateCartItemForm(request.POST)
    if not form.is_valid():
        messages.error(request, "تعداد وارد شده نامعتبر است.")
        return redirect("cart:detail")

    try:
        set_quantity(
            customer_id=customer.pk,
            item_id=item_id,
            quantity=form.cleaned_data["quantity"],
        )
    except CartItem.DoesNotExist:
        raise Http404
    except CartError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, "سبد خرید به‌روزرسانی شد.")
    return redirect("cart:detail")


@login_required
@require_POST
def remove(request, item_id):
    customer = customer_for_user(request.user)
    try:
        remove_item(customer_id=customer.pk, item_id=item_id)
    except CartItem.DoesNotExist:
        raise Http404
    messages.success(request, "قلم از سبد خرید حذف شد.")
    return redirect("cart:detail")
