"""Input validation helpers shared by API routes."""

import re
from decimal import Decimal, InvalidOperation


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
MOBILE_PATTERN = re.compile(r"^[6-9]\d{9}$")
PINCODE_PATTERN = re.compile(r"^\d{6}$")
UPI_PATTERN = re.compile(r"^[\w.\-]{2,}@[a-zA-Z]{2,}$")
VALID_STATES = {
    "Andhra Pradesh",
    "Karnataka",
    "Kerala",
    "Maharashtra",
    "Puducherry",
    "Tamil Nadu",
    "Telangana",
    "Other",
}
PACK_PRICES = {
    "250 g": "price_250",
    "500 g": "price_500",
    "1 kg": "price_1kg",
}


class ValidationError(ValueError):
    """An invalid client-supplied value."""


def required_text(data, field, label=None, minimum=1, maximum=None):
    value = data.get(field)
    label = label or field.replace("_", " ").capitalize()
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise ValidationError(f"{label} must be at least {minimum} characters.")
    value = value.strip()
    if maximum is not None and len(value) > maximum:
        raise ValidationError(f"{label} must be no more than {maximum} characters.")
    return value


def validate_email(value):
    if not isinstance(value, str):
        raise ValidationError("Enter a valid email address.")
    value = value.strip().lower()
    if len(value) > 254 or not EMAIL_PATTERN.fullmatch(value):
        raise ValidationError("Enter a valid email address.")
    return value


def validate_mobile(value):
    if not isinstance(value, str):
        value = str(value) if value is not None else ""
    value = value.strip()
    if not MOBILE_PATTERN.fullmatch(value):
        raise ValidationError("Enter a valid 10-digit Indian mobile number.")
    return value


def validate_pincode(value):
    value = str(value).strip() if value is not None else ""
    if not PINCODE_PATTERN.fullmatch(value):
        raise ValidationError("Pincode must be exactly 6 digits.")
    return value


def validate_state(value):
    if not isinstance(value, str) or value.strip() not in VALID_STATES:
        raise ValidationError("Select a valid state.")
    return value.strip()


def validate_password(value):
    if not isinstance(value, str) or len(value) < 8:
        raise ValidationError("Password must be at least 8 characters.")
    return value


def validate_positive_integer(value, label):
    if isinstance(value, bool):
        raise ValidationError(f"{label} must be a positive whole number.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a positive whole number.") from None
    if number < 1 or str(number) != str(value).strip():
        raise ValidationError(f"{label} must be a positive whole number.")
    return number


def validate_items(items):
    if not isinstance(items, list) or not items:
        raise ValidationError("At least one order item is required.")
    aggregated = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValidationError("Each item must be an object.")
        product_id = validate_positive_integer(item.get("product_id"), "Product ID")
        size = item.get("size")
        if not isinstance(size, str) or size not in PACK_PRICES:
            raise ValidationError("Item size must be 250 g, 500 g, or 1 kg.")
        quantity = validate_positive_integer(item.get("qty"), "Quantity")
        key = (product_id, size)
        aggregated[key] = aggregated.get(key, 0) + quantity
        if aggregated[key] > 10000:
            raise ValidationError("The requested item quantity is too large.")
    return [
        {"product_id": product_id, "size": size, "qty": quantity}
        for (product_id, size), quantity in aggregated.items()
    ]


def validate_nonnegative_decimal(value, label):
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"{label} must be a valid amount.") from None
    if not amount.is_finite() or amount < 0:
        raise ValidationError(f"{label} must be a non-negative amount.")
    return amount
