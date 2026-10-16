from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
)
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import (
    require_POST,
)

from .forms import (
    BusinessSettingsForm,
    TeamMemberAddForm,
    TeamMemberRoleForm,
)
from .models import (
    BusinessInvitation,
    BusinessMember,
)
from .permissions import (
    can_manage_business,
    get_current_membership,
)
from .utils import get_current_business


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


def get_invitation_url(
    request,
    invitation,
):

    relative_url = reverse(
        "businesses:team_invite_accept",
        args=[
            invitation.token,
        ],
    )

    return request.build_absolute_uri(
        relative_url
    )


def send_team_invitation_email(
    request,
    invitation,
):

    invite_url = get_invitation_url(
        request,
        invitation,
    )

    subject = (
        f"You've been invited to "
        f"{invitation.business.name} "
        f"on OrderPilot"
    )

    inviter_name = (
        invitation.invited_by.get_full_name()
        or
        invitation.invited_by.username
        if invitation.invited_by
        else
        "A team administrator"
    )

    message = (
        f"Hello,\n\n"
        f"{inviter_name} invited you to join "
        f"{invitation.business.name} on OrderPilot "
        f"as {invitation.get_role_display()}.\n\n"
        f"Accept your invitation:\n"
        f"{invite_url}\n\n"
        f"This invitation expires on "
        f"{invitation.expires_at.strftime('%d %b %Y at %I:%M %p')}.\n\n"
        f"If you were not expecting this invitation, "
        f"you can ignore this email."
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[
            invitation.email,
        ],
        fail_silently=True,
    )

    if settings.DEBUG:

        print(
            "\n"
            "========================================"
        )

        print(
            "ORDERPILOT TEAM INVITATION"
        )

        print(
            invite_url
        )

        print(
            "========================================"
            "\n"
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
        "business":
            business,

        "membership":
            membership,

        "form":
            form,

        "can_edit":
            can_edit,
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

    # -----------------------------------------------------
    # MARK EXPIRED INVITATIONS
    # -----------------------------------------------------

    pending_invitation_queryset = (
        BusinessInvitation.objects
        .filter(
            business=business,
            status=(
                BusinessInvitation
                .STATUS_PENDING
            ),
        )
        .select_related(
            "invited_by",
        )
    )

    for invitation in pending_invitation_queryset:

        invitation.mark_expired_if_needed()

    pending_invitations = (
        BusinessInvitation.objects
        .filter(
            business=business,
            status=(
                BusinessInvitation
                .STATUS_PENDING
            ),
            expires_at__gt=timezone.now(),
        )
        .select_related(
            "invited_by",
        )
        .order_by(
            "-created_at",
        )
    )

    add_form = TeamMemberAddForm(
        business=business,
        current_membership=membership,
    )

    context = {
        "business":
            business,

        "membership":
            membership,

        "members":
            members,

        "pending_invitations":
            pending_invitations,

        "add_form":
            add_form,

        "can_manage_team":
            can_manage_team(
                membership
            ),
    }

    return render(
        request,
        "businesses/team_members.html",
        context,
    )


# =========================================================
# ADD / INVITE TEAM MEMBER
# =========================================================

@login_required
@require_POST
@transaction.atomic
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

        email = (
            form.cleaned_data[
                "email"
            ]
        )

        role = (
            form.cleaned_data[
                "role"
            ]
        )

        existing_user = (
            form.get_existing_user()
        )

        # -------------------------------------------------
        # EXISTING ORDERPILOT USER
        # -------------------------------------------------

        if existing_user:

            BusinessMember.objects.create(
                business=business,
                user=existing_user,
                role=role,
                is_active=True,
            )

            messages.success(
                request,
                (
                    f"{existing_user.username} "
                    f"was added to the team "
                    f"as {role.title()}."
                ),
            )

            return redirect(
                "businesses:team"
            )

        # -------------------------------------------------
        # NEW USER → CREATE INVITATION
        # -------------------------------------------------

        invitation = (
            BusinessInvitation.objects
            .create(
                business=business,
                email=email,
                role=role,
                invited_by=request.user,
                expires_at=(
                    timezone.now()
                    + timedelta(
                        days=7
                    )
                ),
            )
        )

        transaction.on_commit(
            lambda: (
                send_team_invitation_email(
                    request,
                    invitation,
                )
            )
        )

        messages.success(
            request,
            (
                f"Invitation sent to "
                f"{email}. "
                f"It will expire in 7 days."
            ),
        )

    else:

        error_data = (
            form.errors
            .get_json_data()
        )

        first_message = None

        for field_errors in (
            error_data.values()
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
            (
                first_message
                or
                "Unable to invite team member."
            ),
        )

    return redirect(
        "businesses:team"
    )


# =========================================================
# ACCEPT TEAM INVITATION
# =========================================================

def team_invite_accept(
    request,
    token,
):

    invitation = get_object_or_404(
        BusinessInvitation.objects
        .select_related(
            "business",
            "invited_by",
        ),
        token=token,
    )

    # -----------------------------------------------------
    # ALREADY USED / CANCELLED
    # -----------------------------------------------------

    if (
        invitation.status
        != BusinessInvitation.STATUS_PENDING
    ):

        messages.error(
            request,
            (
                "This invitation is no longer "
                "available."
            ),
        )

        if request.user.is_authenticated:

            return redirect(
                "core:dashboard"
            )

        return redirect(
            "core:login"
        )

    # -----------------------------------------------------
    # EXPIRED
    # -----------------------------------------------------

    if invitation.is_expired:

        invitation.mark_expired_if_needed()

        messages.error(
            request,
            (
                "This invitation has expired. "
                "Please ask the team owner "
                "to send a new invitation."
            ),
        )

        if request.user.is_authenticated:

            return redirect(
                "core:dashboard"
            )

        return redirect(
            "core:login"
        )

    # -----------------------------------------------------
    # ANONYMOUS USER → SIGNUP
    # -----------------------------------------------------

    if not request.user.is_authenticated:

        signup_url = reverse(
            "core:signup"
        )

        return redirect(
            (
                f"{signup_url}"
                f"?invite={invitation.token}"
            )
        )

    # -----------------------------------------------------
    # LOGGED-IN USER MUST MATCH EMAIL
    # -----------------------------------------------------

    if (
        request.user.email
        .strip()
        .lower()
        !=
        invitation.email
        .strip()
        .lower()
    ):

        messages.error(
            request,
            (
                "This invitation was sent "
                "to a different email address."
            ),
        )

        return redirect(
            "core:dashboard"
        )

    # -----------------------------------------------------
    # CREATE / RESTORE MEMBERSHIP
    # -----------------------------------------------------

    membership = (
        BusinessMember.objects
        .filter(
            business=invitation.business,
            user=request.user,
        )
        .first()
    )

    if membership:

        membership.role = (
            invitation.role
        )

        membership.is_active = True

        membership.save(
            update_fields=[
                "role",
                "is_active",
            ]
        )

    else:

        BusinessMember.objects.create(
            business=invitation.business,
            user=request.user,
            role=invitation.role,
            is_active=True,
        )

    invitation.status = (
        BusinessInvitation.STATUS_ACCEPTED
    )

    invitation.accepted_at = (
        timezone.now()
    )

    invitation.save(
        update_fields=[
            "status",
            "accepted_at",
            "updated_at",
        ]
    )

    messages.success(
        request,
        (
            f"You joined "
            f"{invitation.business.name} "
            f"successfully."
        ),
    )

    return redirect(
        "core:dashboard"
    )


# =========================================================
# CANCEL INVITATION
# =========================================================

@login_required
@require_POST
@transaction.atomic
def team_invite_cancel(
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
                "to cancel team invitations."
            ),
        )

        return redirect(
            "businesses:team"
        )

    invitation = get_object_or_404(
        BusinessInvitation.objects
        .select_for_update(),
        pk=pk,
        business=business,
    )

    if (
        invitation.status
        != BusinessInvitation.STATUS_PENDING
    ):

        messages.info(
            request,
            (
                "This invitation is no longer "
                "pending."
            ),
        )

        return redirect(
            "businesses:team"
        )

    # Admins may only manage Staff invites.
    if (
        membership.role
        == BusinessMember.ROLE_ADMIN
        and
        invitation.role
        != BusinessMember.ROLE_STAFF
    ):

        messages.error(
            request,
            (
                "Admins can only manage "
                "Staff invitations."
            ),
        )

        return redirect(
            "businesses:team"
        )

    invitation.status = (
        BusinessInvitation.STATUS_CANCELLED
    )

    invitation.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    messages.success(
        request,
        (
            f"Invitation for "
            f"{invitation.email} "
            f"was cancelled."
        ),
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

    if (
        member.user_id
        == request.user.id
    ):

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
            (
                "Invalid team member role."
            ),
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

    if (
        member.user_id
        == request.user.id
    ):

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