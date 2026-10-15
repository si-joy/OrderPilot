from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
)
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import (
    require_POST,
)

from .forms import (
    BusinessSettingsForm,
    TeamMemberAddForm,
    TeamMemberRoleForm,
)
from .models import BusinessMember
from .utils import get_current_business
from .permissions import (
    can_manage_business,
    get_current_membership,
)


# =========================================================
# HELPERS
# =========================================================

def can_manage_team(
    membership,
):
    return (
        membership
        and
        membership.role
        in {
            BusinessMember.ROLE_OWNER,
            BusinessMember.ROLE_ADMIN,
        }
    )


# =========================================================
# BUSINESS SETTINGS
# =========================================================

@login_required
def business_settings(request):
    business = get_current_business(
        request.user
    )

    membership = get_current_membership(
        request.user,
        business,
    )

    can_edit = bool(
        membership
        and membership.role
        in {
            BusinessMember.ROLE_OWNER,
            BusinessMember.ROLE_ADMIN,
        }
    )

    if request.method == "POST":

        if not can_edit:

            messages.error(
                request,
                (
                    "You do not have permission "
                    "to update business settings."
                ),
            )

            return redirect(
                "businesses:settings"
            )

        old_logo = None

        if business.logo:
            old_logo = business.logo

        form = BusinessSettingsForm(
            request.POST,
            request.FILES,
            instance=business,
        )

        if form.is_valid():

            updated_business = form.save()

            # =============================================
            # DELETE OLD LOGO SAFELY
            # Local storage + Cloudinary compatible
            # =============================================

            if (
                old_logo
                and old_logo.name
                and updated_business.logo
                and updated_business.logo.name
                and old_logo.name
                != updated_business.logo.name
            ):

                try:

                    old_logo.storage.delete(
                        old_logo.name
                    )

                except Exception:
                    pass

            messages.success(
                request,
                (
                    "Business settings were "
                    "updated successfully."
                ),
            )

            return redirect(
                "businesses:settings"
            )

    else:

        form = BusinessSettingsForm(
            instance=business,
        )

    context = {
        "business": business,
        "membership": membership,
        "form": form,
        "can_edit": can_edit,
    }

    return render(
        request,
        "businesses/settings.html",
        context,
    )

# =========================================================
# TEAM MEMBERS
# =========================================================

@login_required
def team_members(request):
    business = get_current_business(
        request.user
    )

    membership = (
        get_current_membership(
            request.user,
            business,
        )
    )

    members = (
        BusinessMember.objects
        .filter(
            business=business,
        )
        .select_related(
            "user",
        )
        .order_by(
            "-is_active",
            "role",
            "user__username",
        )
    )

    add_form = TeamMemberAddForm(
        business=business,
        current_membership=membership,
    )

    context = {
        "business": business,
        "membership": membership,
        "members": members,
        "add_form": add_form,
        "can_manage_team": (
            can_manage_team(
                membership
            )
        ),
    }

    return render(
        request,
        "businesses/team_members.html",
        context,
    )


# =========================================================
# ADD TEAM MEMBER
# =========================================================

@login_required
@require_POST
def team_member_add(request):
    business = get_current_business(
        request.user
    )

    membership = (
        get_current_membership(
            request.user,
            business,
        )
    )

    if not can_manage_team(
        membership
    ):
        messages.error(
            request,
            (
                "You do not have permission "
                "to add team members."
            ),
        )

        return redirect(
            "businesses:team"
        )

    form = TeamMemberAddForm(
        request.POST,
        business=business,
        current_membership=membership,
    )

    if form.is_valid():

        user = form.get_user()

        BusinessMember.objects.create(
            business=business,
            user=user,
            role=form.cleaned_data[
                "role"
            ],
            is_active=True,
        )

        messages.success(
            request,
            (
                f"{user.username} was added "
                "to the team."
            ),
        )

    else:

        error_message = (
            form.errors
            .get_json_data()
        )

        first_message = None

        for field_errors in (
            error_message.values()
        ):
            if field_errors:
                first_message = (
                    field_errors[0][
                        "message"
                    ]
                )
                break

        messages.error(
            request,
            first_message
            or
            "Unable to add team member.",
        )

    return redirect(
        "businesses:team"
    )


# =========================================================
# UPDATE TEAM MEMBER ROLE
# =========================================================

@login_required
@require_POST
@transaction.atomic
def team_member_role_update(
    request,
    pk,
):
    business = get_current_business(
        request.user
    )

    membership = (
        get_current_membership(
            request.user,
            business,
        )
    )

    if not can_manage_team(
        membership
    ):
        messages.error(
            request,
            (
                "You do not have permission "
                "to update team roles."
            ),
        )

        return redirect(
            "businesses:team"
        )

    member = get_object_or_404(
        BusinessMember.objects
        .select_for_update(),
        pk=pk,
        business=business,
    )

    if member.user_id == request.user.id:
        messages.error(
            request,
            (
                "You cannot change your own "
                "role."
            ),
        )

        return redirect(
            "businesses:team"
        )

    if (
        member.role
        == BusinessMember.ROLE_OWNER
    ):
        messages.error(
            request,
            (
                "The owner role cannot be "
                "changed here."
            ),
        )

        return redirect(
            "businesses:team"
        )

    if (
        membership.role
        == BusinessMember.ROLE_ADMIN
    ):
        messages.error(
            request,
            (
                "Admins cannot change team "
                "member roles."
            ),
        )

        return redirect(
            "businesses:team"
        )

    form = TeamMemberRoleForm(
        request.POST
    )

    if form.is_valid():
        member.role = (
            form.cleaned_data[
                "role"
            ]
        )

        member.save(
            update_fields=[
                "role",
            ]
        )

        messages.success(
            request,
            (
                "Team member role was "
                "updated."
            ),
        )

    else:
        messages.error(
            request,
            "Invalid team member role.",
        )

    return redirect(
        "businesses:team"
    )


# =========================================================
# DEACTIVATE TEAM MEMBER
# =========================================================

@login_required
@require_POST
@transaction.atomic
def team_member_deactivate(
    request,
    pk,
):
    business = get_current_business(
        request.user
    )

    membership = (
        get_current_membership(
            request.user,
            business,
        )
    )

    if not can_manage_team(
        membership
    ):
        messages.error(
            request,
            (
                "You do not have permission "
                "to deactivate team members."
            ),
        )

        return redirect(
            "businesses:team"
        )

    member = get_object_or_404(
        BusinessMember.objects
        .select_for_update(),
        pk=pk,
        business=business,
    )

    if member.user_id == request.user.id:
        messages.error(
            request,
            (
                "You cannot deactivate your "
                "own membership."
            ),
        )

        return redirect(
            "businesses:team"
        )

    if (
        member.role
        == BusinessMember.ROLE_OWNER
    ):
        messages.error(
            request,
            (
                "The business owner cannot "
                "be deactivated."
            ),
        )

        return redirect(
            "businesses:team"
        )

    if (
        membership.role
        == BusinessMember.ROLE_ADMIN
        and
        member.role
        != BusinessMember.ROLE_STAFF
    ):
        messages.error(
            request,
            (
                "Admins can only deactivate "
                "Staff members."
            ),
        )

        return redirect(
            "businesses:team"
        )

    if not member.is_active:
        messages.info(
            request,
            (
                "This team member is already "
                "inactive."
            ),
        )

        return redirect(
            "businesses:team"
        )

    member.is_active = False

    member.save(
        update_fields=[
            "is_active",
        ]
    )

    messages.success(
        request,
        (
            "Team member was deactivated."
        ),
    )

    return redirect(
        "businesses:team"
    )


# =========================================================
# RESTORE TEAM MEMBER
# =========================================================

@login_required
@require_POST
@transaction.atomic
def team_member_restore(
    request,
    pk,
):
    business = get_current_business(
        request.user
    )

    membership = (
        get_current_membership(
            request.user,
            business,
        )
    )

    if not can_manage_team(
        membership
    ):
        messages.error(
            request,
            (
                "You do not have permission "
                "to restore team members."
            ),
        )

        return redirect(
            "businesses:team"
        )

    member = get_object_or_404(
        BusinessMember.objects
        .select_for_update(),
        pk=pk,
        business=business,
    )

    if (
        membership.role
        == BusinessMember.ROLE_ADMIN
        and
        member.role
        != BusinessMember.ROLE_STAFF
    ):
        messages.error(
            request,
            (
                "Admins can only restore "
                "Staff members."
            ),
        )

        return redirect(
            "businesses:team"
        )

    if member.is_active:
        messages.info(
            request,
            (
                "This team member is already "
                "active."
            ),
        )

        return redirect(
            "businesses:team"
        )

    member.is_active = True

    member.save(
        update_fields=[
            "is_active",
        ]
    )

    messages.success(
        request,
        (
            "Team member was restored."
        ),
    )

    return redirect(
        "businesses:team"
    )