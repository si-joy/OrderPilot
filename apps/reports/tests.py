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


class RefundAwareReportTests(TestCase):

    def setUp(self):

        # =====================================================
        # USERS
        # =====================================================

        self.user = User.objects.create_user(
            username="report_owner",
            email="report@example.com",
            password="testpass123",
        )

        self.other_user = User.objects.create_user(
            username="other_report_owner",
            email="other-report@example.com",
            password="testpass123",
        )

        # =====================================================
        # BUSINESSES
        # =====================================================

        self.business = Business.objects.create(
            name="Report Test Shop",
            slug="report-test-shop",
            is_active=True,
        )

        self.other_business = Business.objects.create(
            name="Other Report Shop",
            slug="other-report-shop",
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
            full_name="Report Customer",
            phone="01710000000",
            email="customer@example.com",
            address="Dhaka",
            city="Dhaka",
            district="Dhaka",
            is_active=True,
        )

        self.other_customer = Customer.objects.create(
            business=self.other_business,
            full_name="Other Customer",
            phone="01810000000",
            email="other@example.com",
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
            name="Report Product",
            sku="REPORT-001",
            selling_price=Decimal("1000.00"),
            cost_price=Decimal("600.00"),
            stock_quantity=20,
            low_stock_threshold=3,
            is_active=True,
        )

        self.other_product = Product.objects.create(
            business=self.other_business,
            name="Other Report Product",
            sku="OTHER-REPORT-001",
            selling_price=Decimal("9000.00"),
            cost_price=Decimal("1000.00"),
            stock_quantity=20,
            low_stock_threshold=3,
            is_active=True,
        )

        # =====================================================
        # DELIVERED ORDER
        #
        # Gross delivered sale = 1100
        # Refund = 300
        # Net sale = 800
        #
        # Product margin:
        # 1000 - 600 = 400
        #
        # Refund-aware profit:
        # 400 - 300 = 100
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
        # ACTIVE ORDER
        #
        # Total = 500
        # Net paid = 150
        # Due = 350
        # =====================================================

        self.active_order = Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,
            status=Order.STATUS_PENDING,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_PARTIAL,
            subtotal=Decimal("500.00"),
            total_amount=Decimal("500.00"),
            paid_amount=Decimal("200.00"),
            refunded_amount=Decimal("50.00"),
        )

        # =====================================================
        # CANCELLED ORDER
        #
        # Its due must not count as active receivable.
        # Refund still counts in total refunded.
        # =====================================================

        self.cancelled_order = Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,
            status=Order.STATUS_CANCELLED,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_REFUNDED,
            subtotal=Decimal("400.00"),
            total_amount=Decimal("400.00"),
            paid_amount=Decimal("200.00"),
            refunded_amount=Decimal("200.00"),
        )

        # =====================================================
        # OTHER BUSINESS DATA
        # =====================================================

        self.other_order = Order.objects.create(
            business=self.other_business,
            customer=self.other_customer,
            created_by=self.other_user,
            status=Order.STATUS_DELIVERED,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_PAID,
            subtotal=Decimal("9000.00"),
            total_amount=Decimal("9000.00"),
            paid_amount=Decimal("9000.00"),
            refunded_amount=Decimal("0.00"),
        )

        OrderItem.objects.create(
            order=self.other_order,
            product=self.other_product,
            product_name=self.other_product.name,
            sku=self.other_product.sku,
            quantity=1,
            unit_price=Decimal("9000.00"),
            unit_cost=Decimal("1000.00"),
        )

        self.client.login(
            username="report_owner",
            password="testpass123",
        )

    # =========================================================
    # TESTS
    # =========================================================

    def test_report_sales_and_collection_are_refund_aware(
        self,
    ):

        response = self.client.get(
            reverse("reports:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context[
                "gross_delivered_sales"
            ],
            Decimal("1100.00"),
        )

        self.assertEqual(
            response.context["total_sales"],
            Decimal("800.00"),
        )

        # Delivered net paid = 800
        # Active net paid = 150
        # Cancelled net paid = 0

        self.assertEqual(
            response.context["total_collected"],
            Decimal("950.00"),
        )

    def test_report_total_refunded_is_correct(
        self,
    ):

        response = self.client.get(
            reverse("reports:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # 300 + 50 + 200

        self.assertEqual(
            response.context["total_refunded"],
            Decimal("550.00"),
        )

    def test_report_outstanding_due_excludes_cancelled_orders(
        self,
    ):

        response = self.client.get(
            reverse("reports:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Delivered due:
        # 1100 - 800 = 300
        #
        # Active pending due:
        # 500 - 150 = 350
        #
        # Cancelled excluded.
        #
        # Total = 650

        self.assertEqual(
            response.context["outstanding_due"],
            Decimal("650.00"),
        )

    def test_report_estimated_profit_accounts_for_refund(
        self,
    ):

        response = self.client.get(
            reverse("reports:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Product revenue = 1000
        # Product cost = 600
        # Delivered refund = 300
        #
        # Estimated profit = 100

        self.assertEqual(
            response.context["estimated_profit"],
            Decimal("100.00"),
        )

        # Other business must not affect report.

        self.assertEqual(
            response.context["delivered_count"],
            1,
        )