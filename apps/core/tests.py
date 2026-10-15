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