from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import (
    Business,
    BusinessMember,
)
from apps.customers.models import Customer
from apps.products.models import Product

from .models import (
    Order,
    OrderItem,
    OrderPayment,
    OrderRefund,
    OrderStatusHistory,
)
from .views import (
    InsufficientStockError,
    sync_order_inventory,
)

from django.db import IntegrityError, transaction


User = get_user_model()


class OrderInventoryTests(TestCase):

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
            address="Chattogram",
            city="Chattogram",
            district="Chattogram",
            is_active=True,
        )

        # =====================================================
        # PRODUCTS
        # =====================================================

        self.product = Product.objects.create(
            business=self.business,
            name="Premium Face Serum",
            sku="SERUM-001",
            selling_price=Decimal("1200.00"),
            cost_price=Decimal("750.00"),
            stock_quantity=10,
            low_stock_threshold=3,
            is_active=True,
        )

        self.other_product = Product.objects.create(
            business=self.other_business,
            name="Other Product",
            sku="OTHER-001",
            selling_price=Decimal("800.00"),
            cost_price=Decimal("500.00"),
            stock_quantity=20,
            low_stock_threshold=3,
            is_active=True,
        )

        # =====================================================
        # ORDER
        # =====================================================

        self.order = Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,
            status=Order.STATUS_PENDING,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_UNPAID,
            subtotal=Decimal("2400.00"),
            discount=Decimal("0.00"),
            delivery_charge=Decimal("100.00"),
            total_amount=Decimal("2500.00"),
            paid_amount=Decimal("0.00"),
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            sku=self.product.sku,
            quantity=2,
            unit_price=self.product.selling_price,
            unit_cost=self.product.cost_price,
        )

        # =====================================================
        # OTHER BUSINESS ORDER
        # =====================================================

        self.other_order = Order.objects.create(
            business=self.other_business,
            customer=self.other_customer,
            created_by=self.other_user,
            status=Order.STATUS_PENDING,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_UNPAID,
            subtotal=Decimal("800.00"),
            total_amount=Decimal("800.00"),
            paid_amount=Decimal("0.00"),
        )

        OrderItem.objects.create(
            order=self.other_order,
            product=self.other_product,
            product_name=self.other_product.name,
            sku=self.other_product.sku,
            quantity=1,
            unit_price=self.other_product.selling_price,
            unit_cost=self.other_product.cost_price,
        )

        # =====================================================
        # LOGIN
        # =====================================================

        self.client.login(
            username="owner1",
            password="testpass123",
        )

    # =========================================================
    # CONFIRM ORDER
    # =========================================================

    def test_confirm_order_deducts_stock(self):

        response = self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": Order.STATUS_CONFIRMED,
                "note": "Confirmed by customer.",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.STATUS_CONFIRMED,
        )

        self.assertTrue(
            self.order.stock_deducted
        )

        self.assertEqual(
            self.product.stock_quantity,
            8,
        )

    # =========================================================
    # CANCEL ORDER
    # =========================================================

    def test_cancel_confirmed_order_restores_stock(self):

        self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": Order.STATUS_CONFIRMED,
            },
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            8,
        )

        response = self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": Order.STATUS_CANCELLED,
                "note": "Customer cancelled.",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.STATUS_CANCELLED,
        )

        self.assertFalse(
            self.order.stock_deducted
        )

        self.assertEqual(
            self.product.stock_quantity,
            10,
        )

    # =========================================================
    # RECONFIRM CANCELLED ORDER
    # =========================================================

    def test_cancelled_order_can_be_reconfirmed_and_stock_deducted_again(
        self,
    ):

        self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": Order.STATUS_CONFIRMED,
            },
        )

        self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": Order.STATUS_CANCELLED,
            },
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            10,
        )

        response = self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": Order.STATUS_CONFIRMED,
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.STATUS_CONFIRMED,
        )

        self.assertTrue(
            self.order.stock_deducted
        )

        self.assertEqual(
            self.product.stock_quantity,
            8,
        )

    # =========================================================
    # DUPLICATE STATUS
    # =========================================================

    def test_repeating_confirmed_status_does_not_deduct_stock_twice(
        self,
    ):

        url = reverse(
            "orders:status_update",
            args=[self.order.pk],
        )

        self.client.post(
            url,
            {
                "status": Order.STATUS_CONFIRMED,
            },
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            8,
        )

        self.client.post(
            url,
            {
                "status": Order.STATUS_CONFIRMED,
            },
        )

        self.product.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            8,
        )

        self.assertTrue(
            self.order.stock_deducted
        )

    # =========================================================
    # DIRECT INVENTORY SYNC
    # =========================================================

    def test_inventory_sync_does_not_deduct_twice(self):

        self.order.status = (
            Order.STATUS_CONFIRMED
        )

        self.order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        sync_order_inventory(
            self.order
        )

        self.product.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            8,
        )

        self.assertTrue(
            self.order.stock_deducted
        )

        sync_order_inventory(
            self.order
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            8,
        )

    # =========================================================
    # INSUFFICIENT STOCK
    # =========================================================

    def test_confirm_order_fails_when_stock_is_insufficient(
        self,
    ):

        self.product.stock_quantity = 1

        self.product.save(
            update_fields=[
                "stock_quantity",
                "updated_at",
            ]
        )

        response = self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": Order.STATUS_CONFIRMED,
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.STATUS_PENDING,
        )

        self.assertFalse(
            self.order.stock_deducted
        )

        self.assertEqual(
            self.product.stock_quantity,
            1,
        )

    def test_sync_inventory_raises_insufficient_stock_error(
        self,
    ):

        self.product.stock_quantity = 1

        self.product.save(
            update_fields=[
                "stock_quantity",
                "updated_at",
            ]
        )

        self.order.status = (
            Order.STATUS_CONFIRMED
        )

        self.order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        with self.assertRaises(
            InsufficientStockError
        ):
            sync_order_inventory(
                self.order
            )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            1,
        )

    # =========================================================
    # STATUS HISTORY
    # =========================================================

    def test_status_change_creates_history_record(
        self,
    ):

        self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": Order.STATUS_CONFIRMED,
                "note": "Customer confirmed.",
            },
        )

        history = (
            OrderStatusHistory.objects
            .filter(
                order=self.order,
            )
            .latest(
                "created_at"
            )
        )

        self.assertEqual(
            history.from_status,
            Order.STATUS_PENDING,
        )

        self.assertEqual(
            history.to_status,
            Order.STATUS_CONFIRMED,
        )

        self.assertEqual(
            history.changed_by,
            self.user,
        )

        self.assertEqual(
            history.note,
            "Customer confirmed.",
        )

    # =========================================================
    # TENANT ISOLATION
    # =========================================================

    def test_user_cannot_change_other_business_order_status(
        self,
    ):

        response = self.client.post(
            reverse(
                "orders:status_update",
                args=[self.other_order.pk],
            ),
            {
                "status": Order.STATUS_CONFIRMED,
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.other_order.refresh_from_db()
        self.other_product.refresh_from_db()

        self.assertEqual(
            self.other_order.status,
            Order.STATUS_PENDING,
        )

        self.assertEqual(
            self.other_product.stock_quantity,
            20,
        )

    # =========================================================
    # RETURNED ORDER
    # =========================================================

    def test_returned_order_restores_stock(self):

        url = reverse(
            "orders:status_update",
            args=[self.order.pk],
        )

        self.client.post(
            url,
            {
                "status": Order.STATUS_CONFIRMED,
            },
        )

        self.client.post(
            url,
            {
                "status": Order.STATUS_PROCESSING,
            },
        )

        self.client.post(
            url,
            {
                "status": Order.STATUS_SHIPPED,
            },
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            8,
        )

        response = self.client.post(
            url,
            {
                "status": Order.STATUS_RETURNED,
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(
            self.order.status,
            Order.STATUS_RETURNED,
        )

        self.assertFalse(
            self.order.stock_deducted
        )

        self.assertEqual(
            self.product.stock_quantity,
            10,
        )

    # =========================================================
    # AUTHENTICATION
    # =========================================================

    def test_order_pages_require_login(self):

        self.client.logout()

        response = self.client.get(
            reverse(
                "orders:detail",
                args=[self.order.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    # =========================================================
    # PARTIAL PAYMENT
    # =========================================================

    def test_partial_payment_updates_paid_amount_and_status(
        self,
    ):

        response = self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.order.pk],
            ),
            {
                "amount": "1000.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "BKASH-001",
                "note": "Partial payment",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("1000.00"),
        )

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_PARTIAL,
        )

        self.assertEqual(
            self.order.due_amount,
            Decimal("1500.00"),
        )

    # =========================================================
    # FULL PAYMENT
    # =========================================================

    def test_full_payment_marks_order_as_paid(
        self,
    ):

        response = self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.order.pk],
            ),
            {
                "amount": "2500.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "BKASH-FULL",
                "note": "Full payment",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("2500.00"),
        )

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_PAID,
        )

        self.assertEqual(
            self.order.due_amount,
            Decimal("0.00"),
        )

    # =========================================================
    # MULTIPLE PARTIAL PAYMENTS
    # =========================================================

    def test_multiple_partial_payments_accumulate_correctly(
        self,
    ):

        url = reverse(
            "orders:payment_create",
            args=[self.order.pk],
        )

        self.client.post(
            url,
            {
                "amount": "1000.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "PAY-001",
                "note": "",
            },
        )

        self.client.post(
            url,
            {
                "amount": "500.00",
                "payment_method": Order.PAYMENT_NAGAD,
                "reference": "PAY-002",
                "note": "",
            },
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("1500.00"),
        )

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_PARTIAL,
        )

        self.assertEqual(
            self.order.due_amount,
            Decimal("1000.00"),
        )

        self.assertEqual(
            OrderPayment.objects.filter(
                order=self.order,
            ).count(),
            2,
        )

    # =========================================================
    # OVERPAYMENT
    # =========================================================

    def test_payment_cannot_exceed_due_amount(
        self,
    ):

        response = self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.order.pk],
            ),
            {
                "amount": "3000.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "OVERPAY",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("0.00"),
        )

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_UNPAID,
        )

        self.assertFalse(
            OrderPayment.objects.filter(
                order=self.order,
            ).exists()
        )

    # =========================================================
    # FULLY PAID ORDER
    # =========================================================

    def test_fully_paid_order_rejects_extra_payment(
        self,
    ):

        url = reverse(
            "orders:payment_create",
            args=[self.order.pk],
        )

        self.client.post(
            url,
            {
                "amount": "2500.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "FULL-PAY",
                "note": "",
            },
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_PAID,
        )

        response = self.client.post(
            url,
            {
                "amount": "100.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "EXTRA-PAY",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("2500.00"),
        )

        self.assertEqual(
            OrderPayment.objects.filter(
                order=self.order,
            ).count(),
            1,
        )

    # =========================================================
    # CANCELLED ORDER PAYMENT
    # =========================================================

    def test_cancelled_order_rejects_payment(
        self,
    ):

        self.order.status = (
            Order.STATUS_CANCELLED
        )

        self.order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        response = self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.order.pk],
            ),
            {
                "amount": "500.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "CANCELLED-PAY",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("0.00"),
        )

        self.assertFalse(
            OrderPayment.objects.filter(
                order=self.order,
            ).exists()
        )

    # =========================================================
    # RETURNED ORDER PAYMENT
    # =========================================================

    def test_returned_order_rejects_payment(
        self,
    ):

        self.order.status = (
            Order.STATUS_RETURNED
        )

        self.order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        response = self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.order.pk],
            ),
            {
                "amount": "500.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "RETURNED-PAY",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("0.00"),
        )

        self.assertFalse(
            OrderPayment.objects.filter(
                order=self.order,
            ).exists()
        )

    # =========================================================
    # PAYMENT HISTORY
    # =========================================================

    def test_payment_creates_payment_history_record(
        self,
    ):

        self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.order.pk],
            ),
            {
                "amount": "500.00",
                "payment_method": Order.PAYMENT_NAGAD,
                "reference": "NAGAD-123",
                "note": "Advance payment",
            },
        )

        payment = OrderPayment.objects.get(
            order=self.order
        )

        self.assertEqual(
            payment.business,
            self.business,
        )

        self.assertEqual(
            payment.amount,
            Decimal("500.00"),
        )

        self.assertEqual(
            payment.payment_method,
            Order.PAYMENT_NAGAD,
        )

        self.assertEqual(
            payment.reference,
            "NAGAD-123",
        )

        self.assertEqual(
            payment.note,
            "Advance payment",
        )

        self.assertEqual(
            payment.received_by,
            self.user,
        )

    # =========================================================
    # PAYMENT TENANT ISOLATION
    # =========================================================

    def test_user_cannot_record_payment_for_other_business_order(
        self,
    ):

        response = self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.other_order.pk],
            ),
            {
                "amount": "500.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "INVALID-BUSINESS",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.other_order.refresh_from_db()

        self.assertEqual(
            self.other_order.paid_amount,
            Decimal("0.00"),
        )

        self.assertFalse(
            OrderPayment.objects.filter(
                order=self.other_order,
            ).exists()
        )
    

    def test_database_blocks_refund_above_paid_amount(
        self,
    ):

        self.order.paid_amount = Decimal("1000.00")
        self.order.refunded_amount = Decimal("0.00")

        self.order.save(
            update_fields=[
                "paid_amount",
                "refunded_amount",
                "updated_at",
            ]
        )

        with self.assertRaises(IntegrityError):

            with transaction.atomic():

                Order.objects.filter(
                    pk=self.order.pk
                ).update(
                    refunded_amount=Decimal(
                        "1200.00"
                    )
                )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("1000.00"),
        )

        self.assertEqual(
            self.order.refunded_amount,
            Decimal("0.00"),
        )

        # =========================================================
    # REFUND TEST HELPERS
    # =========================================================

    def _record_full_payment(self):

        self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.order.pk],
            ),
            {
                "amount": "2500.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "FULL-PAYMENT",
                "note": "Full payment before refund.",
            },
        )

        self.order.refresh_from_db()

    # =========================================================
    # REFUND TESTS
    # =========================================================

    def test_partial_refund_updates_refunded_amount_and_status(
        self,
    ):

        self._record_full_payment()

        response = self.client.post(
            reverse(
                "orders:refund_create",
                args=[self.order.pk],
            ),
            {
                "amount": "500.00",
                "refund_method": Order.PAYMENT_BKASH,
                "reference": "REFUND-001",
                "note": "Partial refund",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("2500.00"),
        )

        self.assertEqual(
            self.order.refunded_amount,
            Decimal("500.00"),
        )

        self.assertEqual(
            self.order.net_paid_amount,
            Decimal("2000.00"),
        )

        self.assertEqual(
            self.order.refundable_amount,
            Decimal("2000.00"),
        )

        self.assertEqual(
            self.order.due_amount,
            Decimal("500.00"),
        )

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_PARTIAL,
        )

    def test_full_refund_marks_order_as_refunded(
        self,
    ):

        self._record_full_payment()

        response = self.client.post(
            reverse(
                "orders:refund_create",
                args=[self.order.pk],
            ),
            {
                "amount": "2500.00",
                "refund_method": Order.PAYMENT_BKASH,
                "reference": "REFUND-FULL",
                "note": "Full refund",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.refunded_amount,
            Decimal("2500.00"),
        )

        self.assertEqual(
            self.order.net_paid_amount,
            Decimal("0.00"),
        )

        self.assertEqual(
            self.order.refundable_amount,
            Decimal("0.00"),
        )

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_REFUNDED,
        )

        self.assertEqual(
            self.order.due_amount,
            Decimal("2500.00"),
        )

    def test_refund_cannot_exceed_refundable_amount(
        self,
    ):

        self._record_full_payment()

        response = self.client.post(
            reverse(
                "orders:refund_create",
                args=[self.order.pk],
            ),
            {
                "amount": "3000.00",
                "refund_method": Order.PAYMENT_BKASH,
                "reference": "OVER-REFUND",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.refunded_amount,
            Decimal("0.00"),
        )

        self.assertFalse(
            OrderRefund.objects.filter(
                order=self.order,
            ).exists()
        )

    def test_multiple_refunds_accumulate_correctly(
        self,
    ):

        self._record_full_payment()

        url = reverse(
            "orders:refund_create",
            args=[self.order.pk],
        )

        self.client.post(
            url,
            {
                "amount": "500.00",
                "refund_method": Order.PAYMENT_BKASH,
                "reference": "REFUND-A",
                "note": "",
            },
        )

        self.client.post(
            url,
            {
                "amount": "700.00",
                "refund_method": Order.PAYMENT_NAGAD,
                "reference": "REFUND-B",
                "note": "",
            },
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.refunded_amount,
            Decimal("1200.00"),
        )

        self.assertEqual(
            self.order.net_paid_amount,
            Decimal("1300.00"),
        )

        self.assertEqual(
            self.order.refundable_amount,
            Decimal("1300.00"),
        )

        self.assertEqual(
            self.order.due_amount,
            Decimal("1200.00"),
        )

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_PARTIAL,
        )

        self.assertEqual(
            OrderRefund.objects.filter(
                order=self.order,
            ).count(),
            2,
        )

    def test_fully_refunded_order_rejects_extra_refund(
        self,
    ):

        self._record_full_payment()

        url = reverse(
            "orders:refund_create",
            args=[self.order.pk],
        )

        self.client.post(
            url,
            {
                "amount": "2500.00",
                "refund_method": Order.PAYMENT_BKASH,
                "reference": "REFUND-FULL",
                "note": "",
            },
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_REFUNDED,
        )

        response = self.client.post(
            url,
            {
                "amount": "100.00",
                "refund_method": Order.PAYMENT_BKASH,
                "reference": "EXTRA-REFUND",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.refunded_amount,
            Decimal("2500.00"),
        )

        self.assertEqual(
            OrderRefund.objects.filter(
                order=self.order,
            ).count(),
            1,
        )

    def test_refund_creates_refund_history_record(
        self,
    ):

        self._record_full_payment()

        self.client.post(
            reverse(
                "orders:refund_create",
                args=[self.order.pk],
            ),
            {
                "amount": "500.00",
                "refund_method": Order.PAYMENT_NAGAD,
                "reference": "NAGAD-REF-123",
                "note": "Customer refund",
            },
        )

        refund = OrderRefund.objects.get(
            order=self.order
        )

        self.assertEqual(
            refund.business,
            self.business,
        )

        self.assertEqual(
            refund.amount,
            Decimal("500.00"),
        )

        self.assertEqual(
            refund.refund_method,
            Order.PAYMENT_NAGAD,
        )

        self.assertEqual(
            refund.reference,
            "NAGAD-REF-123",
        )

        self.assertEqual(
            refund.note,
            "Customer refund",
        )

        self.assertEqual(
            refund.refunded_by,
            self.user,
        )

    def test_user_cannot_refund_other_business_order(
        self,
    ):

        self.other_order.paid_amount = (
            Decimal("800.00")
        )

        self.other_order.payment_status = (
            Order.PAYMENT_PAID
        )

        self.other_order.save(
            update_fields=[
                "paid_amount",
                "payment_status",
                "updated_at",
            ]
        )

        response = self.client.post(
            reverse(
                "orders:refund_create",
                args=[self.other_order.pk],
            ),
            {
                "amount": "500.00",
                "refund_method": Order.PAYMENT_BKASH,
                "reference": "INVALID-REFUND",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.other_order.refresh_from_db()

        self.assertEqual(
            self.other_order.refunded_amount,
            Decimal("0.00"),
        )

        self.assertFalse(
            OrderRefund.objects.filter(
                order=self.other_order,
            ).exists()
        )

    def test_refund_from_partial_payment_is_limited_to_net_paid_amount(
        self,
    ):

        self.client.post(
            reverse(
                "orders:payment_create",
                args=[self.order.pk],
            ),
            {
                "amount": "1000.00",
                "payment_method": Order.PAYMENT_BKASH,
                "reference": "PARTIAL-PAY",
                "note": "",
            },
        )

        response = self.client.post(
            reverse(
                "orders:refund_create",
                args=[self.order.pk],
            ),
            {
                "amount": "1000.00",
                "refund_method": Order.PAYMENT_BKASH,
                "reference": "PARTIAL-REFUND",
                "note": "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            Decimal("1000.00"),
        )

        self.assertEqual(
            self.order.refunded_amount,
            Decimal("1000.00"),
        )

        self.assertEqual(
            self.order.net_paid_amount,
            Decimal("0.00"),
        )

        self.assertEqual(
            self.order.refundable_amount,
            Decimal("0.00"),
        )

        self.assertEqual(
            self.order.payment_status,
            Order.PAYMENT_REFUNDED,
        )

        self.assertEqual(
            self.order.due_amount,
            Decimal("2500.00"),
        )