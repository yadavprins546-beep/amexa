from django import template

from india_store.models import IndiaOrderNotification

register = template.Library()


@register.inclusion_tag(
    "india_store/partials/notification_link.html",
    takes_context=True,
)
def india_notifications_link(context):
    user = context.get("user")
    unread_count = 0

    if user is not None and user.is_authenticated:
        unread_count = IndiaOrderNotification.objects.filter(
            user=user,
            is_read=False,
        ).count()

    return {"unread_count": unread_count}
