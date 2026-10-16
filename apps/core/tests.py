from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import (
    Business,
    BusinessMember,
)
from apps.customers.models import Customer
from apps.orders.models import (
    Order,
    OrderItem,
)
from apps.products.models import Product


User = get_user_model()


class DashboardRefundAwareTests(TestCase):

    def setUp(self):

        # =====================================================
        # USERS
        # =====================================================

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

        # =====================================================
        # BUSINESSES
        # =====================================================

        self.business = Business.objects.create(
            name="OrderPilot Test Shop",
            slug="orderpilot-test-shop",
            is_active=True,
        )

        self.other_business = Business.objects.create(
            name="Other Shop",
            slug="other-shop-dashboard",
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

        # =====================================================
        # CUSTOMERS
        # =====================================================

        self.customer = Customer.objects.create(
            business=self.business,
            full_name="Rahim Uddin",
            phone="01700000000",
            email="rahim@example.com",
            address="Dhaka",
            city="Dhaka",
            district="Dhaka",
            is_active=True,
        )

        self.other_customer = Customer.objects.create(
            business=self.other_business,
            full_name="Karim Hasan",
            phone="01800000000",
            email="karim@example.com",
            address="Dhaka",
            city="Dhaka",
            district="Dhaka",
            is_active=True,
        )

        # =====================================================
        # PRODUCTS
        # =====================================================

        self.product = Product.objects.create(
            business=self.business,
            name="Test Product",
            sku="TEST-001",
            selling_price=Decimal("1000.00"),
            cost_price=Decimal("600.00"),
            stock_quantity=20,
            low_stock_threshold=3,
            is_active=True,
        )

        self.other_product = Product.objects.create(
            business=self.other_business,
            name="Other Product",
            sku="OTHER-DASH-001",
            selling_price=Decimal("5000.00"),
            cost_price=Decimal("1000.00"),
            stock_quantity=20,
            low_stock_threshold=3,
            is_active=True,
        )

        # =====================================================
        # DELIVERED ORDER
        #
        # Total:      1100
        # Paid:       1100
        # Refunded:    300
        # Net Paid:    800
        # Net Sales:   800
        # =====================================================

        self.delivered_order = Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,
            status=Order.STATUS_DELIVERED,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_PARTIAL,
            subtotal=Decimal("1000.00"),
            discount=Decimal("0.00"),
            delivery_charge=Decimal("100.00"),
            total_amount=Decimal("1100.00"),
            paid_amount=Decimal("1100.00"),
            refunded_amount=Decimal("300.00"),
        )

        OrderItem.objects.create(
            order=self.delivered_order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            quantity=1,
            unit_price=Decimal("1000.00"),
            unit_cost=Decimal("600.00"),
        )

        # =====================================================
        # ACTIVE PENDING ORDER
        #
        # Total:      500
        # Paid:       200
        # Refunded:    50
        # Net Paid:   150
        # Due:        350
        # =====================================================

        self.pending_order = Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,
            status=Order.STATUS_PENDING,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_PARTIAL,
            subtotal=Decimal("500.00"),
            discount=Decimal("0.00"),
            delivery_charge=Decimal("0.00"),
            total_amount=Decimal("500.00"),
            paid_amount=Decimal("200.00"),
            refunded_amount=Decimal("50.00"),
        )

        # =====================================================
        # OTHER BUSINESS ORDER
        #
        # Must never affect current business dashboard.
        # =====================================================

        self.other_order = Order.objects.create(
            business=self.other_business,
            customer=self.other_customer,
            created_by=self.other_user,
            status=Order.STATUS_DELIVERED,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_PAID,
            subtotal=Decimal("5000.00"),
            total_amount=Decimal("5000.00"),
            paid_amount=Decimal("5000.00"),
            refunded_amount=Decimal("0.00"),
        )

        OrderItem.objects.create(
            order=self.other_order,
            product=self.other_product,
            product_name=self.other_product.name,
            sku=self.other_product.sku,
            quantity=1,
            unit_price=Decimal("5000.00"),
            unit_cost=Decimal("1000.00"),
        )

        self.client.login(
            username="owner1",
            password="testpass123",
        )

    # =========================================================
    # TESTS
    # =========================================================

    def test_dashboard_financial_metrics_are_refund_aware(
        self,
    ):

        response = self.client.get(
            reverse("core:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context["total_sales"],
            Decimal("800.00"),
        )

        self.assertEqual(
            response.context["total_collected"],
            Decimal("950.00"),
        )

        self.assertEqual(
            response.context["total_refunded"],
            Decimal("350.00"),
        )

    def test_dashboard_cod_receivable_uses_refund_aware_due(
        self,
    ):

        response = self.client.get(
            reverse("core:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Delivered order due:
        # 1100 - (1100 - 300) = 300
        #
        # Pending order due:
        # 500 - (200 - 50) = 350
        #
        # Total COD receivable = 650

        self.assertEqual(
            response.context["cod_pending"],
            Decimal("650.00"),
        )

    def test_dashboard_excludes_other_business_financial_data(
        self,
    ):

        response = self.client.get(
            reverse("core:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context["total_orders"],
            2,
        )

        self.assertEqual(
            response.context["delivered_orders"],
            1,
        )

        self.assertEqual(
            response.context["total_sales"],
            Decimal("800.00"),
        )

        self.assertNotEqual(
            response.context["total_collected"],
            Decimal("5950.00"),
        )


class AuthSecurityTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="securityowner",
            email="security@example.com",
            password="StrongPass123!",
        )

        self.business = Business.objects.create(
            name="Security Shop",
            slug="security-shop",
            is_active=True,
        )

        BusinessMember.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMember.ROLE_OWNER,
            is_active=True,
        )

    # =========================================================
    # LOGIN
    # =========================================================

    def test_login_page_loads(
        self,
    ):

        response = self.client.get(
            reverse(
                "core:login"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )


    def test_valid_login_redirects_to_dashboard(
        self,
    ):

        response = self.client.post(
            reverse(
                "core:login"
            ),
            {
                "username":
                    "securityowner",

                "password":
                    "StrongPass123!",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            "/",
        )


    def test_invalid_login_does_not_authenticate(
        self,
    ):

        response = self.client.post(
            reverse(
                "core:login"
            ),
            {
                "username":
                    "securityowner",

                "password":
                    "wrong-password",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            response.wsgi_request.user.is_authenticated
        )


    def test_authenticated_user_is_redirected_from_login(
        self,
    ):

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "core:login"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    # =========================================================
    # PROTECTED PAGES
    # =========================================================

    def test_dashboard_requires_login(
        self,
    ):

        response = self.client.get(
            reverse(
                "core:dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertIn(
            "/login/",
            response.url,
        )


    def test_profile_requires_login(
        self,
    ):

        response = self.client.get(
            reverse(
                "core:profile"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )


    def test_components_demo_requires_login(
        self,
    ):

        response = self.client.get(
            reverse(
                "core:components_demo"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    # =========================================================
    # LOGOUT
    # =========================================================

    def test_logout_requires_post(
        self,
    ):

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "core:logout"
            )
        )

        self.assertEqual(
            response.status_code,
            405,
        )


    def test_logout_post_logs_user_out(
        self,
    ):

        self.client.force_login(
            self.user
        )

        response = self.client.post(
            reverse(
                "core:logout"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            reverse(
                "core:login"
            ),
        )

        response = self.client.get(
            reverse(
                "core:dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    # =========================================================
    # SIGNUP
    # =========================================================

    def test_authenticated_user_cannot_open_signup(
        self,
    ):

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse(
                "core:signup"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            reverse(
                "core:dashboard"
            ),
        )


    def test_signup_creates_owner_business_membership(
        self,
    ):

        response = self.client.post(
            reverse(
                "core:signup"
            ),
            {
                "first_name":
                    "New",

                "last_name":
                    "Owner",

                "email":
                    "newowner@example.com",

                "username":
                    "newowner",

                "business_name":
                    "New Owner Shop",

                "business_phone":
                    "01700000000",

                "password1":
                    "AnotherStrong123!",

                "password2":
                    "AnotherStrong123!",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        new_user = User.objects.get(
            username="newowner"
        )

        membership = BusinessMember.objects.get(
            user=new_user
        )

        self.assertEqual(
            membership.role,
            BusinessMember.ROLE_OWNER,
        )

        self.assertTrue(
            membership.is_active
        )

    # =========================================================
    # PASSWORD
    # =========================================================

    def test_password_change_requires_login(
        self,
    ):

        response = self.client.get(
            reverse(
                "core:password_change"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )


    def test_password_reset_page_is_public(
        self,
    ):

        response = self.client.get(
            reverse(
                "core:password_reset"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    # =========================================================
    # CUSTOM ERROR PAGES
    # =========================================================

    def test_custom_404_page(
        self,
    ):

        response = self.client.get(
            "/this-page-does-not-exist/"
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertContains(
            response,
            "404",
            status_code=404,
        )


class AuthSecurityTests(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            username="securityowner",
            email="security@example.com",
            password="StrongPass123!",
            is_active=True,
        )

        self.business = Business.objects.create(
            name="Security Shop",
            slug="security-shop",
            is_active=True,
        )

        self.membership = BusinessMember.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMember.ROLE_OWNER,
            is_active=True,
        )

    # =========================================================
    # LOGIN
    # =========================================================

    def test_login_page_loads(self):

        response = self.client.get(
            reverse("core:login")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_valid_login_redirects_to_dashboard(self):

        response = self.client.post(
            reverse("core:login"),
            {
                "username": "securityowner",
                "password": "StrongPass123!",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            "/",
        )

    def test_invalid_login_does_not_authenticate(self):

        response = self.client.post(
            reverse("core:login"),
            {
                "username": "securityowner",
                "password": "wrong-password",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            response.wsgi_request.user.is_authenticated
        )

    def test_inactive_user_cannot_login(self):

        self.user.is_active = False
        self.user.save(
            update_fields=["is_active"]
        )

        response = self.client.post(
            reverse("core:login"),
            {
                "username": "securityowner",
                "password": "StrongPass123!",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            response.wsgi_request.user.is_authenticated
        )

    def test_authenticated_user_redirected_from_login(self):

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse("core:login")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    # =========================================================
    # AUTHENTICATED ROUTES
    # =========================================================

    def test_dashboard_requires_login(self):

        response = self.client.get(
            reverse("core:dashboard")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertIn(
            "/login/",
            response.url,
        )

    def test_profile_requires_login(self):

        response = self.client.get(
            reverse("core:profile")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_components_demo_requires_login(self):

        response = self.client.get(
            reverse("core:components_demo")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    def test_password_change_requires_login(self):

        response = self.client.get(
            reverse("core:password_change")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    # =========================================================
    # ACTIVE BUSINESS MEMBERSHIP
    # =========================================================

    def test_inactive_membership_cannot_access_dashboard(self):

        self.membership.is_active = False
        self.membership.save(
            update_fields=["is_active"]
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse("core:dashboard")
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_inactive_business_cannot_access_dashboard(self):

        self.business.is_active = False
        self.business.save(
            update_fields=["is_active"]
        )

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse("core:dashboard")
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    # =========================================================
    # LOGOUT
    # =========================================================

    def test_logout_requires_post(self):

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse("core:logout")
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    def test_logout_post_logs_user_out(self):

        self.client.force_login(
            self.user
        )

        response = self.client.post(
            reverse("core:logout")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            reverse("core:login"),
        )

        dashboard_response = self.client.get(
            reverse("core:dashboard")
        )

        self.assertEqual(
            dashboard_response.status_code,
            302,
        )

    # =========================================================
    # SIGNUP
    # =========================================================

    def test_signup_page_loads_for_anonymous_user(self):

        response = self.client.get(
            reverse("core:signup")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_authenticated_user_cannot_open_signup(self):

        self.client.force_login(
            self.user
        )

        response = self.client.get(
            reverse("core:signup")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            reverse("core:dashboard"),
        )

    def test_signup_creates_owner_membership(self):

        response = self.client.post(
            reverse("core:signup"),
            {
                "first_name": "New",
                "last_name": "Owner",
                "email": "newowner@example.com",
                "username": "newowner",
                "business_name": "New Owner Shop",
                "business_phone": "01700000000",
                "password1": "AnotherStrong123!",
                "password2": "AnotherStrong123!",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        new_user = User.objects.get(
            username="newowner"
        )

        membership = BusinessMember.objects.get(
            user=new_user
        )

        self.assertEqual(
            membership.role,
            BusinessMember.ROLE_OWNER,
        )

        self.assertTrue(
            membership.is_active
        )

        self.assertTrue(
            membership.business.is_active
        )

    def test_duplicate_signup_email_is_rejected(self):

        response = self.client.post(
            reverse("core:signup"),
            {
                "first_name": "Duplicate",
                "last_name": "User",
                "email": "security@example.com",
                "username": "differentusername",
                "business_name": "Duplicate Shop",
                "business_phone": "",
                "password1": "AnotherStrong123!",
                "password2": "AnotherStrong123!",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "already exists",
        )

    # =========================================================
    # PASSWORD RESET
    # =========================================================

    def test_password_reset_page_is_public(self):

        response = self.client.get(
            reverse("core:password_reset")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_password_reset_unknown_email_does_not_error(self):

        response = self.client.post(
            reverse("core:password_reset"),
            {
                "email":
                    "doesnotexist@example.com",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            response.url,
            "/password/reset/done/",
        )

    # =========================================================
    # ERROR HANDLERS
    # =========================================================

    def test_custom_404_page(self):

        with self.settings(
            DEBUG=False
        ):

            response = self.client.get(
                "/this-page-does-not-exist/"
            )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.assertContains(
            response,
            "404",
            status_code=404,
        )

    def test_custom_403_page(self):

        self.membership.is_active = False
        self.membership.save(
            update_fields=["is_active"]
        )

        self.client.force_login(
            self.user
        )

        with self.settings(
            DEBUG=False
        ):

            response = self.client.get(
                reverse("core:dashboard")
            )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertContains(
            response,
            "403",
            status_code=403,
        )