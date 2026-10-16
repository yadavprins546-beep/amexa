from django.db import transaction
from django.utils import timezone

from customer.models import Wallet
from .models import (
    IndiaCoinTransaction,
    IndiaOrder,
    IndiaOrderReward,
    IndiaShoppingSettings,
)


def grant_delivery_rewards(order):
    """
    Award delivery coins once and create a Diwali gift entitlement when enabled.
    This function never marks an order as Delivered; the caller must do that.
    """
    if not getattr(order, "pk", None):
        return None

    with transaction.atomic():
        locked_order = IndiaOrder.objects.select_for_update().get(pk=order.pk)

        if locked_order.status != "Delivered":
            return None

        if not locked_order.delivered_at:
            locked_order.delivered_at = timezone.now()
            locked_order.save(update_fields=["delivered_at", "updated_at"])

        settings = IndiaShoppingSettings.get_settings()

        reward, _ = IndiaOrderReward.objects.get_or_create(
            order=locked_order,
            defaults={"gift_status": "NOT_ELIGIBLE"},
        )

        reward_fields = []

        if settings.coins_enabled and reward.coins_awarded_at is None:
            idempotency_key = f"india-order:{locked_order.pk}:delivery-reward"

            ledger = IndiaCoinTransaction.objects.filter(
                idempotency_key=idempotency_key
            ).first()

            if ledger is None:
                coins = sum(
                    int(item.product.reward_coins or 0) * int(item.quantity)
                    for item in locked_order.items.select_related("product").all()
                )

                if coins > 0:
                    wallet, _ = Wallet.objects.get_or_create(user=locked_order.user)
                    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

                    # Recheck after locking the wallet, before changing its balance.
                    ledger = IndiaCoinTransaction.objects.filter(
                        idempotency_key=idempotency_key
                    ).first()

                    if ledger is None:
                        new_balance = int(wallet.coin_balance or 0) + coins
                        wallet.coin_balance = new_balance
                        wallet.lifetime_earned = (
                            int(wallet.lifetime_earned or 0) + coins
                        )
                        wallet.save(
                            update_fields=[
                                "coin_balance",
                                "lifetime_earned",
                                "updated_at",
                            ]
                        )

                        ledger = IndiaCoinTransaction.objects.create(
                            wallet=wallet,
                            order=locked_order,
                            transaction_type="CREDIT",
                            reason="DELIVERY_REWARD",
                            coins=coins,
                            balance_after=new_balance,
                            idempotency_key=idempotency_key,
                            description=(
                                f"BYXOM delivery reward for "
                                f"{locked_order.order_number}"
                            ),
                        )

            if ledger is not None:
                reward.coins_awarded = ledger.coins
                reward.coins_awarded_at = ledger.created_at
            else:
                # Record a completed zero-coin calculation so it is not repeated.
                reward.coins_awarded = 0
                reward.coins_awarded_at = timezone.now()

            reward_fields.extend(["coins_awarded", "coins_awarded_at"])

        if (
            settings.diwali_gift_enabled
            and reward.gift_status == "NOT_ELIGIBLE"
        ):
            reward.gift_name = settings.diwali_gift_name
            reward.gift_description = settings.diwali_gift_description
            reward.gift_status = "ELIGIBLE"
            reward_fields.extend(
                ["gift_name", "gift_description", "gift_status"]
            )

        if reward_fields:
            reward.save(update_fields=reward_fields + ["updated_at"])

        return reward
