from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal("0.01")


def calculate_pricing(price, tax_rate, discounts):
    gross_price = Decimal(price).quantize(CENT, rounding=ROUND_HALF_UP)
    rate = Decimal(tax_rate)
    remaining_total = gross_price
    applied_discounts = []

    for discount in discounts:
        value = Decimal(str(discount["value"])).quantize(CENT, rounding=ROUND_HALF_UP)
        if discount["type"] == "PERCENTAGE":
            if value > Decimal("100.00"):
                raise ValueError("Un descuento porcentual no puede superar el 100 %.")
            amount = (remaining_total * value / Decimal("100")).quantize(
                CENT,
                rounding=ROUND_HALF_UP,
            )
        elif discount["type"] == "FIXED":
            amount = value
        else:
            raise ValueError("El tipo de descuento no es válido.")

        if amount > remaining_total:
            raise ValueError("Los descuentos no pueden superar el total restante.")
        applied_discounts.append({
            "type": discount["type"],
            "value": format(value, "f"),
            "amount": format(amount, "f"),
            "description": str(discount.get("description", "")).strip(),
        })
        remaining_total -= amount

    discount_amount = gross_price - remaining_total
    taxable_base = (remaining_total / (Decimal("1.00") + rate / Decimal("100"))).quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )
    tax_amount = remaining_total - taxable_base
    return {
        "taxable_base": taxable_base,
        "discount_amount": discount_amount,
        "tax_amount": tax_amount,
        "total_price": remaining_total,
        "discounts": applied_discounts,
    }


def legacy_discount(discount_type, discount_value):
    value = Decimal(discount_value)
    if not value:
        return []
    return [{"type": discount_type, "value": str(value)}]
