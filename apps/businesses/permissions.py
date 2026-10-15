from functools import wraps

from django.core.exceptions import PermissionDenied

from .models import BusinessMember
from .utils import get_current_business


# =========================================================
# ROLE GROUPS
# =========================================================

OWNER_ONLY = {
    BusinessMember.ROLE_OWNER,
}

MANAGEMENT_ROLES = {
    BusinessMember.ROLE_OWNER,
    BusinessMember.ROLE_ADMIN,
}

OPERATIONAL_ROLES = {
    BusinessMember.ROLE_OWNER,
    BusinessMember.ROLE_ADMIN,
    BusinessMember.ROLE_STAFF,
}


# =========================================================
# CURRENT MEMBERSHIP
# =========================================================

def get_current_membership(
    user,
    business=None,
):

    if not user.is_authenticated:
        raise PermissionDenied(
            "Authentication required."
        )

    if business is None:
        business = get_current_business(
            user
        )

    membership = (
        BusinessMember.objects
        .select_related(
            "business",
            "user",
        )
        .filter(
            user=user,
            business=business,
            is_active=True,
            business__is_active=True,
        )
        .first()
    )

    if not membership:
        raise PermissionDenied(
            "You are not an active member "
            "of this business."
        )

    return membership


# =========================================================
# ROLE CHECK
# =========================================================

def has_business_role(
    user,
    allowed_roles,
    business=None,
):

    try:

        membership = (
            get_current_membership(
                user,
                business,
            )
        )

    except PermissionDenied:

        return False

    return (
        membership.role
        in allowed_roles
    )


# =========================================================
# OWNER CHECK
# =========================================================

def is_business_owner(
    user,
    business=None,
):

    return has_business_role(
        user,
        OWNER_ONLY,
        business,
    )


# =========================================================
# MANAGEMENT CHECK
# =========================================================

def can_manage_business(
    user,
    business=None,
):

    return has_business_role(
        user,
        MANAGEMENT_ROLES,
        business,
    )


# =========================================================
# OPERATIONAL ACCESS
# =========================================================

def can_access_operations(
    user,
    business=None,
):

    return has_business_role(
        user,
        OPERATIONAL_ROLES,
        business,
    )


# =========================================================
# ROLE REQUIRED DECORATOR
# =========================================================

def business_role_required(
    *allowed_roles,
):

    allowed_roles = set(
        allowed_roles
    )

    def decorator(
        view_func,
    ):

        @wraps(
            view_func
        )
        def wrapped_view(
            request,
            *args,
            **kwargs,
        ):

            business = (
                get_current_business(
                    request.user
                )
            )

            membership = (
                get_current_membership(
                    request.user,
                    business,
                )
            )

            if (
                membership.role
                not in allowed_roles
            ):

                raise PermissionDenied(
                    (
                        "You do not have permission "
                        "to perform this action."
                    )
                )

            request.current_business = (
                business
            )

            request.current_membership = (
                membership
            )

            return view_func(
                request,
                *args,
                **kwargs,
            )

        return wrapped_view

    return decorator


# =========================================================
# CONVENIENCE DECORATORS
# =========================================================

owner_required = (
    business_role_required(
        BusinessMember.ROLE_OWNER,
    )
)


management_required = (
    business_role_required(
        BusinessMember.ROLE_OWNER,
        BusinessMember.ROLE_ADMIN,
    )
)


operational_required = (
    business_role_required(
        BusinessMember.ROLE_OWNER,
        BusinessMember.ROLE_ADMIN,
        BusinessMember.ROLE_STAFF,
    )
)