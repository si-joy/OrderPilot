from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import Business, BusinessMember

from .models import Customer


User = get_user_model()


class CustomerModuleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner1",
            email="owner1@example.com",
            password="testpass123",
        )

        self.other_user = User.objects.create_user(
            username="owner2",
            email="owner2@example.com",
            password="testpass123",
        )

        self.business = Business.objects.create(
            name="LiveHaat",
            slug="livehaat",
            is_active=True,
        )

        self.other_business = Business.objects.create(
            name="Other Shop",
            slug="other-shop",
            is_active=True,
        )

        BusinessMember.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMember.ROLE_OWNER,
            is_active=True,
        )

        BusinessMember.objects.create(
            user=self.other_user,
            business=self.other_business,
            role=BusinessMember.ROLE_OWNER,
            is_active=True,
        )

        self.customer = Customer.objects.create(
            business=self.business,
            full_name="Rahim Uddin",
            phone="01700000000",
            email="rahim@example.com",
            city="Dhaka",
            district="Dhaka",
            is_active=True,
        )

        self.other_customer = Customer.objects.create(
            business=self.other_business,
            full_name="Karim Hasan",
            phone="01800000000",
            email="karim@example.com",
            city="Chattogram",
            district="Chattogram",
            is_active=True,
        )

        self.client.login(
            username="owner1",
            password="testpass123",
        )

    def test_customer_list_only_shows_current_business_customers(self):
        response = self.client.get(
            reverse("customers:list")
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Rahim Uddin",
        )

        self.assertNotContains(
            response,
            "Karim Hasan",
        )

    def test_user_cannot_view_other_business_customer(self):
        response = self.client.get(
            reverse(
                "customers:detail",
                args=[self.other_customer.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_user_cannot_edit_other_business_customer(self):
        response = self.client.get(
            reverse(
                "customers:update",
                args=[self.other_customer.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_customer_creation_assigns_current_business(self):
        response = self.client.post(
            reverse("customers:create"),
            {
                "full_name": "New Customer",
                "phone": "01900000000",
                "email": "new@example.com",
                "address": "Dhaka",
                "city": "Dhaka",
                "district": "Dhaka",
                "notes": "",
                "is_active": "on",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        customer = Customer.objects.get(
            phone="01900000000"
        )

        self.assertEqual(
            customer.business,
            self.business,
        )

    def test_customer_update_works_for_current_business(self):
        response = self.client.post(
            reverse(
                "customers:update",
                args=[self.customer.pk],
            ),
            {
                "full_name": "Rahim Updated",
                "phone": "01700000000",
                "email": "rahim@example.com",
                "address": "",
                "city": "Dhaka",
                "district": "Dhaka",
                "notes": "",
                "is_active": "on",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.customer.refresh_from_db()

        self.assertEqual(
            self.customer.full_name,
            "Rahim Updated",
        )

    def test_archive_customer(self):
        response = self.client.post(
            reverse(
                "customers:archive",
                args=[self.customer.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.customer.refresh_from_db()

        self.assertFalse(
            self.customer.is_active
        )

    def test_restore_customer(self):
        self.customer.is_active = False
        self.customer.save()

        response = self.client.post(
            reverse(
                "customers:restore",
                args=[self.customer.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.customer.refresh_from_db()

        self.assertTrue(
            self.customer.is_active
        )

    def test_customer_pages_require_login(self):
        self.client.logout()

        response = self.client.get(
            reverse("customers:list")
        )

        self.assertEqual(
            response.status_code,
            302,
        )