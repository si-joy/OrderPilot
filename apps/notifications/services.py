from .models import Notification


def create_notification(
    *,
    business,
    title,
    message,
    notification_type=Notification.TYPE_INFO,
    url="",
    user=None,
    event_key="",
):
    """
    Create a business notification.

    If event_key is supplied, the same logical event
    will not create duplicate unread notifications.
    """

    if event_key:

        existing = (
            Notification.objects
            .filter(
                business=business,
                event_key=event_key,
                is_read=False,
            )
            .first()
        )

        if existing:
            return existing

    return Notification.objects.create(
        business=business,
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        url=url,
        event_key=event_key,
    )