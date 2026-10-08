from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import SignupForm, TopUpForm
from .permissions import customer_for_user
from .services import WalletError, top_up


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("/")
    else:
        form = SignupForm()
    return render(request, "registration/signup.html", {"form": form})


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
                return redirect("accounts:payment")
    else:
        form = TopUpForm()
    return render(request, "payment.html", {"form": form, "customer": customer})
