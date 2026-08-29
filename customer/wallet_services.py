from calendar import monthrange
from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.utils import timezone

from .models import MasterOrder, Referral, Wallet, WalletTransaction

REFERRAL_REWARD_COINS = 50


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def calculate_order_reward_coins(product_subtotal):
    subtotal = Decimal(product_subtotal or 0)

    if subtotal <= 0:
        return 0

    if subtotal <= Decimal("300.00"):
        rate = Decimal("0.04")
    elif subtotal <= Decimal("500.00"):
        rate = Decimal("0.03")
    else:
        rate = Decimal("0.025")

    reward = (subtotal * rate).quantize(
        Decimal("1"),
        rounding=ROUND_DOWN,
    )
    return max(0, int(reward))


def _get_locked_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return Wallet.objects.select_for_update().get(pk=wallet.pk)


def expire_wallet_coins(user):
    now = timezone.now()
    expired_total = 0

    with transaction.atomic():
        wallet = _get_locked_wallet(user)

        lots = (
            WalletTransaction.objects
            .select_for_update()
            .filter(
                wallet=wallet,
                transaction_type="CREDIT",
                remaining_coins__gt=0,
                expires_at__isnull=False,
                expires_at__lte=now,
            )
            .order_by("expires_at", "created_at", "id")
        )

        for lot in lots:
            expired_total += lot.remaining_coins
            lot.remaining_coins = 0
            lot.save(update_fields=["remaining_coins"])

        if expired_total:
            wallet.coin_balance = max(
                0,
                wallet.coin_balance - expired_total,
            )
            wallet.save(
                update_fields=["coin_balance", "updated_at"]
            )

            WalletTransaction.objects.create(
                wallet=wallet,
                transaction_type="DEBIT",
                reason="EXPIRED",
                coins=expired_total,
                balance_after=wallet.coin_balance,
                remaining_coins=0,
                description="AMEXA Coins expired after 3 months",
            )

    return expired_total


def credit_coins(
    user,
    coins,
    reason,
    description="",
    master_order=None,
    validity_months=3,
):
    coins = int(coins or 0)

    if coins <= 0:
        return None

    with transaction.atomic():
        wallet = _get_locked_wallet(user)

        # Idempotency: one order reward / referral reward per MasterOrder.
        if reason in {"ORDER_REWARD", "REFERRAL"} and master_order is not None:
            existing = (
                WalletTransaction.objects
                .filter(
                    wallet=wallet,
                    transaction_type="CREDIT",
                    reason=reason,
                    master_order=master_order,
                )
                .first()
            )
            if existing:
                return existing

        wallet.coin_balance += coins
        wallet.lifetime_earned += coins
        wallet.save(
            update_fields=[
                "coin_balance",
                "lifetime_earned",
                "updated_at",
            ]
        )

        now = timezone.now()

        return WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="CREDIT",
            reason=reason,
            coins=coins,
            balance_after=wallet.coin_balance,
            master_order=master_order,
            description=description,
            remaining_coins=coins,
            expires_at=_add_months(now, validity_months),
        )


def redeem_coins(
    user,
    coins,
    master_order=None,
    description="",
    skip_expiry=False,
):
    requested = int(coins or 0)

    if requested <= 0:
        raise ValueError("Coins must be greater than 0.")

    if not skip_expiry:
        expire_wallet_coins(user)

    with transaction.atomic():
        wallet = _get_locked_wallet(user)
        now = timezone.now()

        if wallet.coin_balance < requested:
            raise ValueError("Not enough AMEXA Coins.")

        lots = list(
            WalletTransaction.objects
            .select_for_update()
            .filter(
                wallet=wallet,
                transaction_type="CREDIT",
                remaining_coins__gt=0,
                expires_at__gt=now,
            )
            .order_by("expires_at", "created_at", "id")
        )

        if sum(lot.remaining_coins for lot in lots) < requested:
            raise ValueError("Not enough valid AMEXA Coins.")

        left = requested

        for lot in lots:
            if left <= 0:
                break

            used = min(lot.remaining_coins, left)
            lot.remaining_coins -= used
            left -= used
            lot.save(update_fields=["remaining_coins"])

        wallet.coin_balance -= requested
        wallet.lifetime_spent += requested
        wallet.save(
            update_fields=[
                "coin_balance",
                "lifetime_spent",
                "updated_at",
            ]
        )

        return WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="DEBIT",
            reason="REDEEM",
            coins=requested,
            balance_after=wallet.coin_balance,
            master_order=master_order,
            description=description
            or f"₹{requested} discount using AMEXA Coins",
            remaining_coins=0,
        )


def refund_redeemed_coins(master_order):
    """
    Refund redeemed coins only when the whole MasterOrder is Cancelled.
    Prevents double refunds.
    """
    with transaction.atomic():
        master_order = (
            MasterOrder.objects
            .select_for_update()
            .select_related("user")
            .get(pk=master_order.pk)
        )

        if master_order.status != "Cancelled":
            return None

        redeemed = (
            WalletTransaction.objects
            .filter(
                wallet__user=master_order.user,
                transaction_type="DEBIT",
                reason="REDEEM",
                master_order=master_order,
            )
            .first()
        )

        if not redeemed:
            return None

        existing_refund = (
            WalletTransaction.objects
            .filter(
                wallet__user=master_order.user,
                transaction_type="CREDIT",
                reason="REFUND",
                master_order=master_order,
            )
            .first()
        )

        if existing_refund:
            return existing_refund

        return credit_coins(
            master_order.user,
            redeemed.coins,
            "REFUND",
            f"Coins refunded for cancelled order {master_order.master_order_number}",
            master_order=master_order,
            validity_months=3,
        )


def reverse_order_reward(master_order):
    """
    Safety helper for a MasterOrder that had already received an order reward
    but is later made invalid/cancelled. Normally Delivered orders cannot be
    customer-cancelled, but this protects admin/back-office changes too.
    """
    with transaction.atomic():
        master_order = (
            MasterOrder.objects
            .select_for_update()
            .select_related("user")
            .get(pk=master_order.pk)
        )

        reward_tx = (
            WalletTransaction.objects
            .select_for_update()
            .filter(
                wallet__user=master_order.user,
                transaction_type="CREDIT",
                reason="ORDER_REWARD",
                master_order=master_order,
            )
            .first()
        )

        if not reward_tx:
            return None

        existing = (
            WalletTransaction.objects
            .filter(
                wallet=reward_tx.wallet,
                transaction_type="DEBIT",
                reason="REVERSAL",
                master_order=master_order,
            )
            .first()
        )
        if existing:
            return existing

        wallet = _get_locked_wallet(master_order.user)

        # Only reverse coins still available from this reward lot.
        reversible = min(
            reward_tx.remaining_coins,
            wallet.coin_balance,
        )

        if reversible <= 0:
            return None

        reward_tx.remaining_coins -= reversible
        reward_tx.save(update_fields=["remaining_coins"])

        wallet.coin_balance -= reversible
        wallet.save(update_fields=["coin_balance", "updated_at"])

        return WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="DEBIT",
            reason="REVERSAL",
            coins=reversible,
            balance_after=wallet.coin_balance,
            master_order=master_order,
            remaining_coins=0,
            description=(
                f"Order reward reversed for "
                f"{master_order.master_order_number}"
            ),
        )


def reward_referral_if_eligible(master_order):
    try:
        referral = (
            Referral.objects
            .select_for_update()
            .get(
                referred_user=master_order.user,
                is_rewarded=False,
            )
        )
    except Referral.DoesNotExist:
        return None

    # The qualifying order itself must be fully completed.
    if master_order.status != "Completed":
        return None

    # If an earlier completed MasterOrder exists, this is not the first one.
    earlier = (
        MasterOrder.objects
        .filter(
            user=master_order.user,
            status="Completed",
            created_at__lt=master_order.created_at,
        )
        .exists()
    )

    if earlier:
        return None

    tx = credit_coins(
        referral.referrer,
        referral.reward_coins or REFERRAL_REWARD_COINS,
        "REFERRAL",
        (
            "Referral reward after first successful order by "
            f"{master_order.user}"
        ),
        master_order,
    )

    referral.is_rewarded = True
    referral.rewarded_at = timezone.now()
    referral.qualifying_master_order = master_order
    referral.save(
        update_fields=[
            "is_rewarded",
            "rewarded_at",
            "qualifying_master_order",
        ]
    )

    return tx


def reward_completed_master_order(master_order_id):
    with transaction.atomic():
        master_order = (
            MasterOrder.objects
            .select_for_update()
            .select_related("user")
            .get(pk=master_order_id)
        )

        orders = master_order.shop_orders.all()

        # STRICT RULE: every child shop order must be Delivered.
        # Pending / Confirmed / Cancelled / any other state does not qualify.
        if (
            not orders.exists()
            or orders.exclude(status="Delivered").exists()
        ):
            return None

        if master_order.status != "Completed":
            master_order.status = "Completed"
            master_order.save(
                update_fields=["status", "updated_at"]
            )

        coins = calculate_order_reward_coins(
            master_order.subtotal
        )

        tx = None
        if coins:
            tx = credit_coins(
                master_order.user,
                coins,
                "ORDER_REWARD",
                (
                    "Order reward for "
                    f"{master_order.master_order_number}"
                ),
                master_order,
            )

        reward_referral_if_eligible(master_order)
        return tx
