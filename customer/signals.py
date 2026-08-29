import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order
from .wallet_services import reward_completed_master_order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def amexa_order_delivered_wallet_reward(sender, instance, **kwargs):
    if instance.status != "Delivered" or not instance.master_order_id:
        return

    try:
        reward_completed_master_order(instance.master_order_id)
    except Exception:
        # Order status save must remain successful even if the reward service
        # has an unexpected error. The error remains visible in server logs.
        logger.exception(
            "AMEXA Coins reward failed for MasterOrder %s",
            instance.master_order_id,
        )
