from django import forms


class CheckoutForm(forms.Form):
    checkout_key = forms.UUIDField()
