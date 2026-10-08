from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import SignupForm, TopUpForm
from .permissions import customer_for_user
from .services import WalletError, top_up


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            if form.cleaned_data["role"] == SignupForm.ROLE_SELLER:
                return redirect("shops:seller_dashboard")
            return redirect("accounts:customer_dashboard")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


class RoleAwareLoginView(auth_views.LoginView):
    """Send each role to its own panel unless a `next` target was requested."""

    template_name = "registration/login.html"

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        user = self.request.user
        if getattr(user, "seller_profile", None) is not None:
            return reverse("shops:seller_dashboard")
        if getattr(user, "customer_profile", None) is not None:
            return reverse("accounts:customer_dashboard")
        return super().get_success_url()


@login_required
def customer_dashboard(request):
    customer = customer_for_user(request.user)
    return render(request, "customer/dashboard.html", {"customer": customer})


@login_required
def payment(request):
    customer = customer_for_user(request.user)
    if request.method == "POST":
        form = TopUpForm(request.POST)
        if form.is_valid():
            try:
                top_up(customer_id=customer.pk, amount=form.cleaned_data["amount"])
            except WalletError as error:
                form.add_error(None, error.message)
            else:
                messages.success(request, "موجودی کیف پول افزایش یافت (پرداخت آزمایشی).")
                return redirect("accounts:payment")
    else:
        form = TopUpForm()
    return render(request, "payment.html", {"form": form, "customer": customer})
