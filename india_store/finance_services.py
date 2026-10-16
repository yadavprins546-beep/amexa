from django.db import transaction
from django.utils import timezone

from .models import FinanceTransaction


def record_customer_payment(payment):
    """
    Record a paid customer payment.
    Existing finance records are reused to avoid duplicates.
    Bank settlement verification remains a separate step.
    """
    if payment.payment_status != "Paid":
        return None, False

    master_order = payment.master_order
    reference = (
        payment.transaction_id
        or f"legacy-payment-{payment.pk}"
    )

    method_map = {
        "COD": "cash",
        "UPI": "upi",
        "CARD": "card",
        "NETBANKING": "other",
        "WALLET": "other",
    }

    defaults = {
        "direction": "incoming",
        "transaction_type": "customer_payment",
        "payment_source": "system",
        "order_reference": master_order.master_order_number,
        "transaction_reference": reference,
        "status": "successful",
        "party_type": "customer",
        "party_name": (
            getattr(payment.user, "name", "")
            or getattr(payment.user, "email", "")
            or "Customer"
        ),
        "amount": payment.amount,
        "payment_method": method_map.get(
            payment.payment_method,
            "other",
        ),
        "payment_provider": (
            "COD"
            if payment.payment_method == "COD"
            else (payment.gateway_name or "Unknown")
        ),
        "transaction_date": (
            payment.paid_at
            or payment.updated_at
            or timezone.now()
        ),
        "is_verified": False,
        "notes": (
            f"Linked to customer.Payment id={payment.pk}. "
            "Reconcile with external bank/gateway evidence separately."
        ),
    }

    with transaction.atomic():
        existing = FinanceTransaction.objects.filter(
            source_payment=payment
        ).first()

        if existing:
            return existing, False

        matches = list(
            FinanceTransaction.objects.select_for_update().filter(
                direction="incoming",
                transaction_type="customer_payment",
                payment_source="system",
                order_reference=master_order.master_order_number,
                transaction_reference=reference,
            )[:2]
        )

        if len(matches) > 1:
            raise ValueError(
                f"Multiple finance records match Payment {payment.pk}."
            )

        if matches:
            record = matches[0]

            if record.source_payment_id not in (None, payment.pk):
                raise ValueError(
                    "Matching finance record is linked to another payment."
                )

            if record.source_payment_id is None:
                record.source_payment = payment
                record.save(
                    update_fields=["source_payment", "updated_at"]
                )

            return record, False

        return FinanceTransaction.objects.get_or_create(
            source_payment=payment,
            defaults=defaults,
        )
