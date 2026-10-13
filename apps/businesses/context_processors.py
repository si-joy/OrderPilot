from .models import BusinessMember


def current_business_context(request):
    if not request.user.is_authenticated:
        return {}

    membership = (
        BusinessMember.objects
        .select_related("business")
        .filter(
            user=request.user,
            is_active=True,
            business__is_active=True,
        )
        .order_by("id")
        .first()
    )

    if not membership:
        return {}

    return {
        "current_business": membership.business,
        "current_membership": membership,
    }