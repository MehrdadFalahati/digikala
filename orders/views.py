from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.permissions import customer_for_user

from . import services
from .forms import CheckoutForm
from .models import Order


@login_required
@require_POST
def checkout(request):
    customer = customer_for_user(request.user)
    form = CheckoutForm(request.POST)
    if not form.is_valid():
        messages.error(request, "درخواست پرداخت نامعتبر است.")
        return redirect("cart:detail")

    try:
        order = services.checkout(
            customer_id=customer.pk,
            checkout_key=form.cleaned_data["checkout_key"],
        )
    except services.CheckoutError as error:
        messages.error(request, error.message)
        return redirect("cart:detail")

    messages.success(request, "پرداخت آزمایشی با موفقیت انجام شد.")
    return redirect("orders:thank_you", order_id=order.pk)


@login_required
def history(request):
    customer = customer_for_user(request.user)
    orders = Order.objects.filter(customer=customer).prefetch_related("items")
    return render(request, "orders/history.html", {"orders": orders})


@login_required
def detail(request, order_id):
    customer = customer_for_user(request.user)
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), pk=order_id, customer=customer
    )
    return render(request, "orders/detail.html", {"order": order})


@login_required
def thank_you(request, order_id):
    customer = customer_for_user(request.user)
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), pk=order_id, customer=customer
    )
    return render(request, "orders/thank_you.html", {"order": order})
