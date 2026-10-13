from django.core.exceptions import PermissionDenied

from .models import BusinessMember


def get_current_business(user):
    if not user.is_authenticated:
        raise PermissionDenied("Authentication required.")

    membership = (
        BusinessMember.objects
        .select_related("business")
        .filter(
            user=user,
            is_active=True,
            business__is_active=True,
        )
        .order_by("id")
        .first()
    )

    if not membership:
        raise PermissionDenied(
            "You are not connected to an active business."
        )

    return membership.business