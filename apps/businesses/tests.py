from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from .models import (
    Business,
    BusinessMember,
)
from .permissions import (
    can_access_operations,
    can_manage_business,
    get_current_membership,
    has_business_role,
    is_business_owner,
)


User = get_user_model()


class BusinessPermissionTests(
    TestCase,
):

    def setUp(
        self,
    ):

        self.owner = (
            User.objects.create_user(
                username="owner",
                password="testpass123",
            )
        )

        self.admin = (
            User.objects.create_user(
                username="admin",
                password="testpass123",
            )
        )

        self.staff = (
            User.objects.create_user(
                username="staff",
                password="testpass123",
            )
        )

        self.outsider = (
            User.objects.create_user(
                username="outsider",
                password="testpass123",
            )
        )

        self.business = (
            Business.objects.create(
                name="LiveHaat",
                slug="livehaat",
                is_active=True,
            )
        )

        self.owner_membership = (
            BusinessMember.objects.create(
                business=self.business,
                user=self.owner,
                role=(
                    BusinessMember
                    .ROLE_OWNER
                ),
                is_active=True,
            )
        )

        self.admin_membership = (
            BusinessMember.objects.create(
                business=self.business,
                user=self.admin,
                role=(
                    BusinessMember
                    .ROLE_ADMIN
                ),
                is_active=True,
            )
        )

        self.staff_membership = (
            BusinessMember.objects.create(
                business=self.business,
                user=self.staff,
                role=(
                    BusinessMember
                    .ROLE_STAFF
                ),
                is_active=True,
            )
        )


    def test_get_current_membership_returns_active_membership(
        self,
    ):

        membership = (
            get_current_membership(
                self.owner,
                self.business,
            )
        )

        self.assertEqual(
            membership,
            self.owner_membership,
        )


    def test_get_current_membership_rejects_outsider(
        self,
    ):

        with self.assertRaises(
            PermissionDenied
        ):

            get_current_membership(
                self.outsider,
                self.business,
            )


    def test_get_current_membership_rejects_inactive_member(
        self,
    ):

        self.staff_membership.is_active = False

        self.staff_membership.save(
            update_fields=[
                "is_active",
            ]
        )

        with self.assertRaises(
            PermissionDenied
        ):

            get_current_membership(
                self.staff,
                self.business,
            )


    def test_owner_is_business_owner(
        self,
    ):

        self.assertTrue(
            is_business_owner(
                self.owner,
                self.business,
            )
        )


    def test_admin_is_not_business_owner(
        self,
    ):

        self.assertFalse(
            is_business_owner(
                self.admin,
                self.business,
            )
        )


    def test_owner_can_manage_business(
        self,
    ):

        self.assertTrue(
            can_manage_business(
                self.owner,
                self.business,
            )
        )


    def test_admin_can_manage_business(
        self,
    ):

        self.assertTrue(
            can_manage_business(
                self.admin,
                self.business,
            )
        )


    def test_staff_cannot_manage_business(
        self,
    ):

        self.assertFalse(
            can_manage_business(
                self.staff,
                self.business,
            )
        )


    def test_staff_can_access_operations(
        self,
    ):

        self.assertTrue(
            can_access_operations(
                self.staff,
                self.business,
            )
        )


    def test_outsider_cannot_access_operations(
        self,
    ):

        self.assertFalse(
            can_access_operations(
                self.outsider,
                self.business,
            )
        )


    def test_has_business_role_matches_exact_role(
        self,
    ):

        self.assertTrue(
            has_business_role(
                self.admin,
                {
                    BusinessMember
                    .ROLE_ADMIN,
                },
                self.business,
            )
        )

        self.assertFalse(
            has_business_role(
                self.staff,
                {
                    BusinessMember
                    .ROLE_ADMIN,
                },
                self.business,
            )
        )