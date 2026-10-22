"""Fixed commission illustrations; this does not collect fees or initiate payouts."""

from decimal import Decimal, ROUND_HALF_UP

COMMISSION_PERCENT = Decimal("10")
PENNY = Decimal("0.01")


def commission_breakdown(amount):
    gross = Decimal(str(amount))
    if not gross.is_finite() or gross < 0:
        raise ValueError(
            "A commission calculation requires a non-negative finite amount."
        )
    gross = gross.quantize(PENNY, rounding=ROUND_HALF_UP)
    commission = (gross * COMMISSION_PERCENT / Decimal("100")).quantize(
        PENNY, rounding=ROUND_HALF_UP
    )
    return {
        "gross": gross,
        "rate": COMMISSION_PERCENT,
        "commission": commission,
        "worker_share": gross - commission,
    }
