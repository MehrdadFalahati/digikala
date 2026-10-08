from django.core.exceptions import PermissionDenied


def customer_for_user(user):
    """Return the customer profile of the user or deny access to other roles."""
    profile = getattr(user, "customer_profile", None)
    if profile is None:
        raise PermissionDenied("این عملیات فقط برای مشتریان مجاز است.")
    return profile


def seller_for_user(user):
    """Return the seller profile of the user or deny access to other roles."""
    profile = getattr(user, "seller_profile", None)
    if profile is None:
        raise PermissionDenied("این عملیات فقط برای فروشندگان مجاز است.")
    return profile
