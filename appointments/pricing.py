from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal("0.01")


def calculate_pricing(price, tax_rate, discounts):
    gross_price = Decimal(price).quantize(CENT, rounding=ROUND_HALF_UP)
    rate = Decimal(tax_rate)
    taxable_base = (gross_price / (Decimal("1.00") + rate / Decimal("100"))).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )
    remaining_base = taxable_base
    applied_discounts = []

    for discount in discounts:
        value = Decimal(str(discount["value"])).quantize(CENT, rounding=ROUND_HALF_UP)
        if discount["type"] == "PERCENTAGE":
            if value > Decimal("100.00"):
                raise ValueError("Un descuento porcentual no puede superar el 100 %.")
            amount = (remaining_base * value / Decimal("100")).quantize(
                CENT,
                rounding=ROUND_HALF_UP,
            )
        elif discount["type"] == "FIXED":
            amount = value
        else:
            raise ValueError("El tipo de descuento no es válido.")

        if amount > remaining_base:
            raise ValueError("Los descuentos no pueden superar la base imponible restante.")
        applied_discounts.append({
            "type": discount["type"],
            "value": format(value, "f"),
            "amount": format(amount, "f"),
            "description": str(discount.get("description", "")).strip(),
        })
        remaining_base -= amount

    discount_amount = taxable_base - remaining_base
    tax_amount = gross_price - taxable_base
    return {
        "taxable_base": taxable_base,
        "discount_amount": discount_amount,
        "tax_amount": tax_amount,
        "total_price": remaining_base + tax_amount,
        "discounts": applied_discounts,
    }


def legacy_discount(discount_type, discount_value):
    value = Decimal(discount_value)
    if not value:
        return []
    return [{"type": discount_type, "value": str(value)}]
