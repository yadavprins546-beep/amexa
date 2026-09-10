from django.db import transaction
from django.utils import timezone

from .models import (
    Order,
    Settlement,
    ShopkeeperWallet,
    ShopkeeperWalletTransaction,
)


def credit_shop_order_earning(order_id):
    """
    Credit shop payable amount once when an order is Delivered.

    Safe/idempotent:
    the same order cannot normally credit the shop wallet twice.
    """

    with transaction.atomic():

        order = (
            Order.objects
            .select_for_update()
            .select_related("shop")
            .get(pk=order_id)
        )

        if order.status != "Delivered":
            return None

        if not order.shop_id:
            return None

        try:
            settlement = (
                Settlement.objects
                .select_for_update()
                .get(order=order)
            )
        except Settlement.DoesNotExist:
            return None

        amount = settlement.shop_payable

        if amount <= 0:
            return None

        wallet, _ = ShopkeeperWallet.objects.get_or_create(
            shop=order.shop
        )

        wallet = (
            ShopkeeperWallet.objects
            .select_for_update()
            .get(pk=wallet.pk)
        )

        existing = (
            ShopkeeperWalletTransaction.objects
            .filter(
                wallet=wallet,
                order=order,
                reason="ORDER_EARNING",
            )
            .first()
        )

        if existing:
            return existing

        wallet.available_balance += amount
        wallet.lifetime_earned += amount

        wallet.save(
            update_fields=[
                "available_balance",
                "lifetime_earned",
                "updated_at",
            ]
        )

        tx = ShopkeeperWalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="CREDIT",
            reason="ORDER_EARNING",
            amount=amount,
            balance_after=wallet.available_balance,
            order=order,
            settlement=settlement,
            description=(
                f"Shop earning credited for "
                f"order {order.order_number}"
            ),
        )

        return tx


def pay_settlement_claim(claim_id, admin_user=None):
    from .models import SettlementClaim

    with transaction.atomic():
        claim = (
            SettlementClaim.objects
            .select_for_update()
            .select_related("wallet", "shop")
            .get(pk=claim_id)
        )

        wallet = (
            ShopkeeperWallet.objects
            .select_for_update()
            .get(pk=claim.wallet_id)
        )

        existing = (
            ShopkeeperWalletTransaction.objects
            .filter(
                wallet=wallet,
                reason="SETTLEMENT_PAID",
                description__icontains=f"Claim #{claim.pk}",
            )
            .first()
        )

        if existing:
            return existing

        if claim.amount <= 0:
            raise ValueError("Claim amount must be greater than zero.")

        if wallet.available_balance < claim.amount:
            raise ValueError(
                "Insufficient shop wallet balance for this settlement claim."
            )

        wallet.available_balance -= claim.amount
        wallet.lifetime_paid += claim.amount

        wallet.save(
            update_fields=[
                "available_balance",
                "lifetime_paid",
                "updated_at",
            ]
        )

        now = timezone.now()

        claim.status = "PAID"
        claim.reviewed_by = admin_user
        claim.reviewed_at = now
        claim.paid_at = now

        claim.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "paid_at",
                "updated_at",
            ]
        )

        tx = ShopkeeperWalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="DEBIT",
            reason="SETTLEMENT_PAID",
            amount=claim.amount,
            balance_after=wallet.available_balance,
            description=f"Settlement Claim #{claim.pk} paid",
            created_by=admin_user,
        )

        return tx
