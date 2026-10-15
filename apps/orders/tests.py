from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import (
    Business,
    BusinessMember,
)
from apps.customers.models import Customer
from apps.products.models import (
    Product,
    StockAdjustment,
)

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

from .forms import OrderItemFormSet



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

        # =========================================================
    # ORDER EDIT HELPERS
    # =========================================================

    def _order_edit_payload(
        self,
        *,
        order=None,
        quantity=None,
        discount=None,
        delivery_charge=None,
        customer=None,
        payment_method=None,
        notes=None,
    ):

        order = order or self.order

        item = order.items.first()

        if quantity is None:
            quantity = item.quantity

        if discount is None:
            discount = order.discount

        if delivery_charge is None:
            delivery_charge = order.delivery_charge

        if customer is None:
            customer = order.customer

        if payment_method is None:
            payment_method = order.payment_method

        if notes is None:
            notes = order.notes

        formset = OrderItemFormSet(
            instance=order,
            form_kwargs={
                "business": order.business,
            },
        )

        prefix = formset.prefix

        return {
            "customer": str(customer.pk),
            "status": order.status,
            "payment_method": payment_method,
            "discount": str(discount),
            "delivery_charge": str(
                delivery_charge
            ),
            "paid_amount": str(
                order.paid_amount
            ),
            "courier_name": (
                order.courier_name
                or ""
            ),
            "tracking_number": (
                order.tracking_number
                or ""
            ),
            "delivery_address": (
                order.delivery_address
                or ""
            ),
            "notes": notes or "",

            f"{prefix}-TOTAL_FORMS": "1",
            f"{prefix}-INITIAL_FORMS": "1",
            f"{prefix}-MIN_NUM_FORMS": "1",
            f"{prefix}-MAX_NUM_FORMS": "1000",

            f"{prefix}-0-id": str(
                item.pk
            ),
            f"{prefix}-0-product": str(
                item.product_id
            ),
            f"{prefix}-0-quantity": str(
                quantity
            ),
        }

    def _change_order_status(
        self,
        status,
    ):

        response = self.client.post(
            reverse(
                "orders:status_update",
                args=[self.order.pk],
            ),
            {
                "status": status,
                "note": "Test status change.",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

    # =========================================================
    # ORDER EDIT TESTS
    # =========================================================

    def test_pending_order_quantity_can_be_edited(
        self,
    ):

        item = self.order.items.first()

        old_quantity = item.quantity

        product = item.product

        old_stock = (
            product.stock_quantity
        )

        new_quantity = (
            old_quantity + 1
        )

        response = self.client.post(
            reverse(
                "orders:edit",
                args=[self.order.pk],
            ),
            self._order_edit_payload(
                quantity=new_quantity,
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        item.refresh_from_db()

        product.refresh_from_db()

        self.assertEqual(
            item.quantity,
            new_quantity,
        )

        # Pending orders do not commit stock.
        self.assertEqual(
            product.stock_quantity,
            old_stock,
        )

        self.assertFalse(
            self.order.stock_deducted
        )

    def test_confirmed_order_quantity_increase_adjusts_stock(
        self,
    ):

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        item = self.order.items.first()

        product = item.product

        product.refresh_from_db()

        stock_after_confirm = (
            product.stock_quantity
        )

        old_quantity = item.quantity

        new_quantity = (
            old_quantity + 1
        )

        response = self.client.post(
            reverse(
                "orders:edit",
                args=[self.order.pk],
            ),
            self._order_edit_payload(
                quantity=new_quantity,
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        item.refresh_from_db()

        product.refresh_from_db()

        self.order.refresh_from_db()

        self.assertEqual(
            item.quantity,
            new_quantity,
        )

        self.assertEqual(
            product.stock_quantity,
            stock_after_confirm - 1,
        )

        self.assertTrue(
            self.order.stock_deducted
        )

    def test_confirmed_order_quantity_decrease_restores_stock(
        self,
    ):

        item = self.order.items.first()

        if item.quantity < 2:

            item.quantity = 2

            item.save(
                update_fields=[
                    "quantity",
                ]
            )

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        item.refresh_from_db()

        product = item.product

        product.refresh_from_db()

        stock_after_confirm = (
            product.stock_quantity
        )

        old_quantity = item.quantity

        new_quantity = (
            old_quantity - 1
        )

        response = self.client.post(
            reverse(
                "orders:edit",
                args=[self.order.pk],
            ),
            self._order_edit_payload(
                quantity=new_quantity,
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        item.refresh_from_db()

        product.refresh_from_db()

        self.order.refresh_from_db()

        self.assertEqual(
            item.quantity,
            new_quantity,
        )

        self.assertEqual(
            product.stock_quantity,
            stock_after_confirm + 1,
        )

        self.assertTrue(
            self.order.stock_deducted
        )

    def test_confirmed_order_edit_rolls_back_when_stock_is_insufficient(
        self,
    ):

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        item = self.order.items.first()

        product = item.product

        item.refresh_from_db()
        product.refresh_from_db()

        original_quantity = (
            item.quantity
        )

        original_stock = (
            product.stock_quantity
        )

        original_total = (
            self.order.total_amount
        )

        # During edit the old stock will first be restored.
        # Request far more than could ever be available.
        impossible_quantity = (
            original_stock
            + original_quantity
            + 100
        )

        response = self.client.post(
            reverse(
                "orders:edit",
                args=[self.order.pk],
            ),
            self._order_edit_payload(
                quantity=(
                    impossible_quantity
                ),
            ),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.order.refresh_from_db()

        item.refresh_from_db()

        product.refresh_from_db()

        # Everything must roll back.
        self.assertEqual(
            item.quantity,
            original_quantity,
        )

        self.assertEqual(
            product.stock_quantity,
            original_stock,
        )

        self.assertEqual(
            self.order.total_amount,
            original_total,
        )

        self.assertTrue(
            self.order.stock_deducted
        )

    def test_shipped_order_product_and_financial_edit_are_locked(
        self,
    ):

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        self._change_order_status(
            Order.STATUS_PROCESSING
        )

        self._change_order_status(
            Order.STATUS_SHIPPED
        )

        item = self.order.items.first()

        item.refresh_from_db()

        original_quantity = (
            item.quantity
        )

        original_discount = (
            self.order.discount
        )

        original_delivery_charge = (
            self.order.delivery_charge
        )

        original_customer_id = (
            self.order.customer_id
        )

        formset = OrderItemFormSet(
            instance=self.order,
            form_kwargs={
                "business": self.business,
            },
        )

        prefix = formset.prefix

        payload = {
            "customer": str(
                self.order.customer_id
            ),
            "status": (
                self.order.status
            ),
            "payment_method": (
                self.order.payment_method
            ),

            # Malicious financial changes.
            "discount": "9999.00",
            "delivery_charge": "9999.00",
            "paid_amount": "0.00",

            "courier_name": (
                self.order.courier_name
                or ""
            ),
            "tracking_number": (
                self.order.tracking_number
                or ""
            ),
            "delivery_address": (
                self.order.delivery_address
                or ""
            ),
            "notes": (
                "Safe operational correction"
            ),

            # Malicious product edit.
            f"{prefix}-TOTAL_FORMS":
                "1",

            f"{prefix}-INITIAL_FORMS":
                "1",

            f"{prefix}-MIN_NUM_FORMS":
                "1",

            f"{prefix}-MAX_NUM_FORMS":
                "1000",

            f"{prefix}-0-id":
                str(item.pk),

            f"{prefix}-0-product":
                str(item.product_id),

            f"{prefix}-0-quantity":
                str(
                    original_quantity + 10
                ),
        }

        response = self.client.post(
            reverse(
                "orders:edit",
                args=[self.order.pk],
            ),
            payload,
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        item.refresh_from_db()

        self.assertEqual(
            item.quantity,
            original_quantity,
        )

        self.assertEqual(
            self.order.discount,
            original_discount,
        )

        self.assertEqual(
            self.order.delivery_charge,
            original_delivery_charge,
        )

        self.assertEqual(
            self.order.customer_id,
            original_customer_id,
        )

        # Safe field should still update.
        self.assertEqual(
            self.order.notes,
            "Safe operational correction",
        )

    def test_order_edit_preserves_payment_and_refund_history(
        self,
    ):

        # Record full payment first.
        self._record_full_payment()

        # Partial refund.
        self.client.post(
            reverse(
                "orders:refund_create",
                args=[self.order.pk],
            ),
            {
                "amount": "500.00",
                "refund_method":
                    Order.PAYMENT_BKASH,
                "reference":
                    "EDIT-REFUND-TEST",
                "note":
                    "Refund before edit.",
            },
        )

        self.order.refresh_from_db()

        paid_before = (
            self.order.paid_amount
        )

        refunded_before = (
            self.order.refunded_amount
        )

        payment_count_before = (
            self.order.payments.count()
        )

        refund_count_before = (
            self.order.refunds.count()
        )

        item = self.order.items.first()

        response = self.client.post(
            reverse(
                "orders:edit",
                args=[self.order.pk],
            ),
            self._order_edit_payload(
                quantity=item.quantity,
                delivery_charge=Decimal(
                    "1000.00"
                ),
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.paid_amount,
            paid_before,
        )

        self.assertEqual(
            self.order.refunded_amount,
            refunded_before,
        )

        self.assertEqual(
            self.order.payments.count(),
            payment_count_before,
        )

        self.assertEqual(
            self.order.refunds.count(),
            refund_count_before,
        )

    def test_order_edit_cannot_reduce_total_below_net_paid_amount(
        self,
    ):

        self._record_full_payment()

        self.order.refresh_from_db()

        original_total = (
            self.order.total_amount
        )

        original_discount = (
            self.order.discount
        )

        item = self.order.items.first()

        # Force calculated total below retained payment.
        huge_discount = (
            item.line_total
            + self.order.delivery_charge
        )

        response = self.client.post(
            reverse(
                "orders:edit",
                args=[self.order.pk],
            ),
            self._order_edit_payload(
                discount=huge_discount,
            ),
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.total_amount,
            original_total,
        )

        self.assertEqual(
            self.order.discount,
            original_discount,
        )

    def test_user_cannot_edit_other_business_order(
        self,
    ):

        response = self.client.get(
            reverse(
                "orders:edit",
                args=[
                    self.other_order.pk
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        # =========================================================
    # ORDER-DRIVEN STOCK AUDIT TESTS
    # =========================================================

    def test_confirmed_order_creates_stock_deduction_history(
        self,
    ):

        item = self.order.items.first()

        product = item.product

        product.refresh_from_db()

        stock_before = (
            product.stock_quantity
        )

        quantity = item.quantity

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        product.refresh_from_db()

        adjustment = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                product=product,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_DEDUCT
                ),
            )
            .latest("id")
        )

        self.assertEqual(
            adjustment.quantity,
            quantity,
        )

        self.assertEqual(
            adjustment.before_quantity,
            stock_before,
        )

        self.assertEqual(
            adjustment.after_quantity,
            stock_before - quantity,
        )

        self.assertEqual(
            adjustment.business,
            self.business,
        )

        self.assertEqual(
            adjustment.adjusted_by,
            self.user,
        )


    def test_cancelled_confirmed_order_creates_stock_restore_history(
        self,
    ):

        item = self.order.items.first()

        product = item.product

        quantity = item.quantity

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        product.refresh_from_db()

        stock_after_confirm = (
            product.stock_quantity
        )

        self._change_order_status(
            Order.STATUS_CANCELLED
        )

        product.refresh_from_db()

        adjustment = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                product=product,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_RESTORE
                ),
            )
            .latest("id")
        )

        self.assertEqual(
            adjustment.quantity,
            quantity,
        )

        self.assertEqual(
            adjustment.before_quantity,
            stock_after_confirm,
        )

        self.assertEqual(
            adjustment.after_quantity,
            stock_after_confirm + quantity,
        )

        self.assertEqual(
            product.stock_quantity,
            stock_after_confirm + quantity,
        )


    def test_returned_order_creates_stock_restore_history(
        self,
    ):

        item = self.order.items.first()

        product = item.product

        quantity = item.quantity

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        self._change_order_status(
            Order.STATUS_PROCESSING
        )

        self._change_order_status(
            Order.STATUS_SHIPPED
        )

        product.refresh_from_db()

        stock_before_return = (
            product.stock_quantity
        )

        self._change_order_status(
            Order.STATUS_RETURNED
        )

        product.refresh_from_db()

        adjustment = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                product=product,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_RESTORE
                ),
            )
            .latest("id")
        )

        self.assertEqual(
            adjustment.quantity,
            quantity,
        )

        self.assertEqual(
            adjustment.before_quantity,
            stock_before_return,
        )

        self.assertEqual(
            adjustment.after_quantity,
            stock_before_return + quantity,
        )

        self.assertEqual(
            adjustment.adjusted_by,
            self.user,
        )


    def test_confirmed_order_edit_creates_restore_and_deduct_history(
        self,
    ):

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        item = self.order.items.first()

        old_quantity = item.quantity

        new_quantity = (
            old_quantity + 1
        )

        before_restore_count = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_RESTORE
                ),
            )
            .count()
        )

        before_deduct_count = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_DEDUCT
                ),
            )
            .count()
        )

        response = self.client.post(
            reverse(
                "orders:edit",
                args=[
                    self.order.pk
                ],
            ),
            self._order_edit_payload(
                quantity=new_quantity,
            ),
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        restore_count = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_RESTORE
                ),
            )
            .count()
        )

        deduct_count = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_DEDUCT
                ),
            )
            .count()
        )

        self.assertEqual(
            restore_count,
            before_restore_count + 1,
        )

        self.assertEqual(
            deduct_count,
            before_deduct_count + 1,
        )

        latest_restore = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_RESTORE
                ),
            )
            .latest("id")
        )

        latest_deduct = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_DEDUCT
                ),
            )
            .latest("id")
        )

        self.assertEqual(
            latest_restore.quantity,
            old_quantity,
        )

        self.assertEqual(
            latest_deduct.quantity,
            new_quantity,
        )


    def test_repeating_confirmed_status_does_not_create_duplicate_stock_history(
        self,
    ):

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        initial_count = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_DEDUCT
                ),
            )
            .count()
        )

        response = self.client.post(
            reverse(
                "orders:status_update",
                args=[
                    self.order.pk
                ],
            ),
            {
                "status":
                    Order.STATUS_CONFIRMED,

                "note":
                    "Repeated status request.",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        final_count = (
            StockAdjustment.objects
            .filter(
                order=self.order,
                adjustment_type=(
                    StockAdjustment
                    .TYPE_ORDER_DEDUCT
                ),
            )
            .count()
        )

        self.assertEqual(
            final_count,
            initial_count,
        )

        # =========================================================
    # ORDER LIST SEARCH / FILTER / PAGINATION TESTS
    # =========================================================

    def test_order_list_search_by_order_number(
        self,
    ):

        response = self.client.get(
            reverse("orders:list"),
            {
                "q": self.order.order_number,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.order.order_number,
        )

        self.assertNotContains(
            response,
            self.other_order.order_number,
        )


    def test_order_list_search_by_customer_name(
        self,
    ):

        response = self.client.get(
            reverse("orders:list"),
            {
                "q": self.order.customer.full_name,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.order.order_number,
        )


    def test_order_list_search_by_customer_phone(
        self,
    ):

        response = self.client.get(
            reverse("orders:list"),
            {
                "q": self.order.customer.phone,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.order.order_number,
        )


    def test_order_list_filters_by_status(
        self,
    ):

        self._change_order_status(
            Order.STATUS_CONFIRMED
        )

        response = self.client.get(
            reverse("orders:list"),
            {
                "status":
                    Order.STATUS_CONFIRMED,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.order.order_number,
        )


    def test_order_list_filters_by_payment_status(
        self,
    ):

        self._record_full_payment()

        self.order.refresh_from_db()

        response = self.client.get(
            reverse("orders:list"),
            {
                "payment_status":
                    Order.PAYMENT_PAID,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.order.order_number,
        )


    def test_order_list_filters_by_date_range(
        self,
    ):

        order_date = (
            self.order.created_at
            .date()
            .isoformat()
        )

        response = self.client.get(
            reverse("orders:list"),
            {
                "date_from":
                    order_date,

                "date_to":
                    order_date,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.order.order_number,
        )


    def test_order_list_does_not_show_other_business_orders(
        self,
    ):

        response = self.client.get(
            reverse("orders:list")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.order.order_number,
        )

        self.assertNotContains(
            response,
            self.other_order.order_number,
        )


    def test_order_list_paginates_results(
        self,
    ):

        customer = self.order.customer

        for index in range(20):

            Order.objects.create(
                business=self.business,
                customer=customer,
                created_by=self.user,
                status=Order.STATUS_PENDING,
                payment_method=(
                    Order.PAYMENT_COD
                ),
                payment_status=(
                    Order.PAYMENT_UNPAID
                ),
                subtotal="100.00",
                discount="0.00",
                delivery_charge="0.00",
                total_amount="100.00",
                paid_amount="0.00",
                refunded_amount="0.00",
                delivery_address="Test",
            )

        response = self.client.get(
            reverse("orders:list")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        page_obj = (
            response.context["page_obj"]
        )

        self.assertEqual(
            len(
                response.context[
                    "orders"
                ]
            ),
            15,
        )

        self.assertTrue(
            page_obj.has_next()
        )


    def test_order_list_filter_query_is_preserved_for_pagination(
        self,
    ):

        response = self.client.get(
            reverse("orders:list"),
            {
                "q": "test search",
                "status":
                    Order.STATUS_PENDING,
                "page": "2",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        filter_query = (
            response.context[
                "filter_query"
            ]
        )

        self.assertIn(
            "q=test+search",
            filter_query,
        )

        self.assertIn(
            "status=pending",
            filter_query,
        )

        self.assertNotIn(
            "page=",
            filter_query,
        )