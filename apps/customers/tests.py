from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import Business, BusinessMember
from apps.orders.models import Order

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

    # =========================================================
    # BASIC CUSTOMER MODULE TESTS
    # =========================================================

    def test_customer_list_only_shows_current_business_customers(
        self,
    ):

        response = self.client.get(
            reverse("customers:list")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Rahim Uddin",
        )

        self.assertNotContains(
            response,
            "Karim Hasan",
        )

    def test_user_cannot_view_other_business_customer(
        self,
    ):

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.other_customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_user_cannot_edit_other_business_customer(
        self,
    ):

        response = self.client.get(
            reverse(
                "customers:update",
                args=[
                    self.other_customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_customer_creation_assigns_current_business(
        self,
    ):

        response = self.client.post(
            reverse(
                "customers:create"
            ),
            {
                "full_name":
                    "New Customer",

                "phone":
                    "01900000000",

                "email":
                    "new@example.com",

                "address":
                    "Dhaka",

                "city":
                    "Dhaka",

                "district":
                    "Dhaka",

                "notes":
                    "",

                "is_active":
                    "on",
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

    def test_customer_update_works_for_current_business(
        self,
    ):

        response = self.client.post(
            reverse(
                "customers:update",
                args=[
                    self.customer.pk,
                ],
            ),
            {
                "full_name":
                    "Rahim Updated",

                "phone":
                    "01700000000",

                "email":
                    "rahim@example.com",

                "address":
                    "",

                "city":
                    "Dhaka",

                "district":
                    "Dhaka",

                "notes":
                    "",

                "is_active":
                    "on",
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

    def test_archive_customer(
        self,
    ):

        response = self.client.post(
            reverse(
                "customers:archive",
                args=[
                    self.customer.pk,
                ],
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

    def test_restore_customer(
        self,
    ):

        self.customer.is_active = False

        self.customer.save(
            update_fields=[
                "is_active",
            ]
        )

        response = self.client.post(
            reverse(
                "customers:restore",
                args=[
                    self.customer.pk,
                ],
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

    def test_customer_pages_require_login(
        self,
    ):

        self.client.logout()

        response = self.client.get(
            reverse(
                "customers:list"
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

    # =========================================================
    # CUSTOMER LIST SEARCH / FILTER / PAGINATION TESTS
    # =========================================================

    def test_customer_list_search_by_name(
        self,
    ):

        response = self.client.get(
            reverse(
                "customers:list"
            ),
            {
                "q":
                    "Rahim",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Rahim Uddin",
        )

        self.assertNotContains(
            response,
            "Karim Hasan",
        )

    def test_customer_list_search_by_phone(
        self,
    ):

        response = self.client.get(
            reverse(
                "customers:list"
            ),
            {
                "q":
                    "01700000000",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Rahim Uddin",
        )

    def test_customer_list_search_by_email(
        self,
    ):

        response = self.client.get(
            reverse(
                "customers:list"
            ),
            {
                "q":
                    "rahim@example.com",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Rahim Uddin",
        )

    def test_customer_list_search_by_city(
        self,
    ):

        response = self.client.get(
            reverse(
                "customers:list"
            ),
            {
                "q":
                    "Dhaka",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Rahim Uddin",
        )

    def test_customer_list_filters_archived_customers(
        self,
    ):

        self.customer.is_active = False

        self.customer.save(
            update_fields=[
                "is_active",
            ]
        )

        response = self.client.get(
            reverse(
                "customers:list"
            ),
            {
                "status":
                    "inactive",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Rahim Uddin",
        )

    def test_customer_list_all_status_shows_active_and_inactive(
        self,
    ):

        archived_customer = (
            Customer.objects.create(
                business=self.business,
                full_name="Archived Customer",
                phone="01600000000",
                email="archived@example.com",
                city="Dhaka",
                district="Dhaka",
                is_active=False,
            )
        )

        response = self.client.get(
            reverse(
                "customers:list"
            ),
            {
                "status":
                    "all",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.customer.full_name,
        )

        self.assertContains(
            response,
            archived_customer.full_name,
        )

    def test_customer_list_paginates_results(
        self,
    ):

        for index in range(
            15
        ):

            Customer.objects.create(
                business=self.business,

                full_name=(
                    f"Customer {index}"
                ),

                phone=(
                    f"01910000"
                    f"{index:03d}"
                ),

                email=(
                    f"customer{index}"
                    "@example.com"
                ),

                is_active=True,
            )

        response = self.client.get(
            reverse(
                "customers:list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        page_obj = (
            response.context[
                "page_obj"
            ]
        )

        self.assertEqual(
            len(
                response.context[
                    "customers"
                ]
            ),
            10,
        )

        self.assertTrue(
            page_obj.has_next()
        )

    def test_customer_filter_query_preserves_search_and_status(
        self,
    ):

        response = self.client.get(
            reverse(
                "customers:list"
            ),
            {
                "q":
                    "Rahim Uddin",

                "status":
                    "all",

                "page":
                    "2",
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
            "q=Rahim+Uddin",
            filter_query,
        )

        self.assertIn(
            "status=all",
            filter_query,
        )

        self.assertNotIn(
            "page=",
            filter_query,
        )

    def test_customer_search_still_respects_business_isolation(
        self,
    ):

        response = self.client.get(
            reverse(
                "customers:list"
            ),
            {
                "q":
                    self.other_customer
                    .full_name,

                "status":
                    "all",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        customers = (
            response.context[
                "customers"
            ]
        )

        self.assertNotIn(
            self.other_customer,
            customers,
        )

        self.assertEqual(
            len(
                customers
            ),
            0,
        )

    # =========================================================
    # CUSTOMER CRM / ACCOUNTING TESTS
    # =========================================================

    def test_customer_detail_delivered_sales_is_refund_aware(
        self,
    ):

        Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,

            status=(
                Order.STATUS_DELIVERED
            ),

            payment_method=(
                Order.PAYMENT_COD
            ),

            payment_status=(
                Order.PAYMENT_PARTIAL
            ),

            subtotal=Decimal(
                "1000.00"
            ),

            discount=Decimal(
                "0.00"
            ),

            delivery_charge=Decimal(
                "0.00"
            ),

            total_amount=Decimal(
                "1000.00"
            ),

            paid_amount=Decimal(
                "1000.00"
            ),

            refunded_amount=Decimal(
                "200.00"
            ),

            delivery_address=(
                "Dhaka"
            ),
        )

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context[
                "delivered_sales"
            ],
            Decimal(
                "800.00"
            ),
        )

    def test_customer_detail_gross_paid_total(
        self,
    ):

        Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,

            status=(
                Order.STATUS_CONFIRMED
            ),

            payment_method=(
                Order.PAYMENT_COD
            ),

            payment_status=(
                Order.PAYMENT_PARTIAL
            ),

            subtotal=Decimal(
                "1000.00"
            ),

            total_amount=Decimal(
                "1000.00"
            ),

            paid_amount=Decimal(
                "600.00"
            ),

            refunded_amount=Decimal(
                "0.00"
            ),

            delivery_address=(
                "Dhaka"
            ),
        )

        Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,

            status=(
                Order.STATUS_DELIVERED
            ),

            payment_method=(
                Order.PAYMENT_COD
            ),

            payment_status=(
                Order.PAYMENT_PAID
            ),

            subtotal=Decimal(
                "500.00"
            ),

            total_amount=Decimal(
                "500.00"
            ),

            paid_amount=Decimal(
                "500.00"
            ),

            refunded_amount=Decimal(
                "0.00"
            ),

            delivery_address=(
                "Dhaka"
            ),
        )

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.context[
                "gross_paid"
            ],
            Decimal(
                "1100.00"
            ),
        )

    def test_customer_detail_total_refunded(
        self,
    ):

        Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,

            status=(
                Order.STATUS_DELIVERED
            ),

            payment_method=(
                Order.PAYMENT_COD
            ),

            payment_status=(
                Order.PAYMENT_PARTIAL
            ),

            subtotal=Decimal(
                "1000.00"
            ),

            total_amount=Decimal(
                "1000.00"
            ),

            paid_amount=Decimal(
                "1000.00"
            ),

            refunded_amount=Decimal(
                "250.00"
            ),

            delivery_address=(
                "Dhaka"
            ),
        )

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.context[
                "total_refunded"
            ],
            Decimal(
                "250.00"
            ),
        )

    def test_customer_detail_net_paid_is_refund_aware(
        self,
    ):

        Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,

            status=(
                Order.STATUS_DELIVERED
            ),

            payment_method=(
                Order.PAYMENT_COD
            ),

            payment_status=(
                Order.PAYMENT_PARTIAL
            ),

            subtotal=Decimal(
                "1000.00"
            ),

            total_amount=Decimal(
                "1000.00"
            ),

            paid_amount=Decimal(
                "900.00"
            ),

            refunded_amount=Decimal(
                "300.00"
            ),

            delivery_address=(
                "Dhaka"
            ),
        )

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.context[
                "net_paid"
            ],
            Decimal(
                "600.00"
            ),
        )

    def test_customer_detail_excludes_cancelled_order_due(
        self,
    ):

        Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,

            status=(
                Order.STATUS_CANCELLED
            ),

            payment_method=(
                Order.PAYMENT_COD
            ),

            payment_status=(
                Order.PAYMENT_UNPAID
            ),

            subtotal=Decimal(
                "1000.00"
            ),

            total_amount=Decimal(
                "1000.00"
            ),

            paid_amount=Decimal(
                "0.00"
            ),

            refunded_amount=Decimal(
                "0.00"
            ),

            delivery_address=(
                "Dhaka"
            ),
        )

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.context[
                "total_due"
            ],
            Decimal(
                "0.00"
            ),
        )

    def test_customer_detail_excludes_returned_order_due(
        self,
    ):

        Order.objects.create(
            business=self.business,
            customer=self.customer,
            created_by=self.user,

            status=(
                Order.STATUS_RETURNED
            ),

            payment_method=(
                Order.PAYMENT_COD
            ),

            payment_status=(
                Order.PAYMENT_PARTIAL
            ),

            subtotal=Decimal(
                "1000.00"
            ),

            total_amount=Decimal(
                "1000.00"
            ),

            paid_amount=Decimal(
                "400.00"
            ),

            refunded_amount=Decimal(
                "0.00"
            ),

            delivery_address=(
                "Dhaka"
            ),
        )

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.context[
                "total_due"
            ],
            Decimal(
                "0.00"
            ),
        )

    def test_customer_detail_repeat_customer_detection(
        self,
    ):

        for index in range(
            2
        ):

            Order.objects.create(
                business=self.business,
                customer=self.customer,
                created_by=self.user,

                status=(
                    Order.STATUS_PENDING
                ),

                payment_method=(
                    Order.PAYMENT_COD
                ),

                payment_status=(
                    Order.PAYMENT_UNPAID
                ),

                subtotal=Decimal(
                    "500.00"
                ),

                total_amount=Decimal(
                    "500.00"
                ),

                paid_amount=Decimal(
                    "0.00"
                ),

                refunded_amount=Decimal(
                    "0.00"
                ),

                delivery_address=(
                    f"Address {index}"
                ),
            )

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertTrue(
            response.context[
                "is_repeat_customer"
            ]
        )

        self.assertEqual(
            response.context[
                "total_orders"
            ],
            2,
        )

    def test_customer_detail_last_order_is_latest_order(
        self,
    ):

        first_order = (
            Order.objects.create(
                business=self.business,
                customer=self.customer,
                created_by=self.user,

                status=(
                    Order.STATUS_PENDING
                ),

                payment_method=(
                    Order.PAYMENT_COD
                ),

                payment_status=(
                    Order.PAYMENT_UNPAID
                ),

                subtotal=Decimal(
                    "500.00"
                ),

                total_amount=Decimal(
                    "500.00"
                ),

                paid_amount=Decimal(
                    "0.00"
                ),

                refunded_amount=Decimal(
                    "0.00"
                ),

                delivery_address=(
                    "First Address"
                ),
            )
        )

        second_order = (
            Order.objects.create(
                business=self.business,
                customer=self.customer,
                created_by=self.user,

                status=(
                    Order.STATUS_PENDING
                ),

                payment_method=(
                    Order.PAYMENT_COD
                ),

                payment_status=(
                    Order.PAYMENT_UNPAID
                ),

                subtotal=Decimal(
                    "700.00"
                ),

                total_amount=Decimal(
                    "700.00"
                ),

                paid_amount=Decimal(
                    "0.00"
                ),

                refunded_amount=Decimal(
                    "0.00"
                ),

                delivery_address=(
                    "Second Address"
                ),
            )
        )

        response = self.client.get(
            reverse(
                "customers:detail",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.context[
                "last_order"
            ],
            second_order,
        )

        self.assertNotEqual(
            response.context[
                "last_order"
            ],
            first_order,
        )

    # =========================================================
    # CUSTOMER ROLE / PERMISSION TESTS
    # =========================================================

    def test_staff_cannot_archive_customer(
        self,
    ):

        staff = User.objects.create_user(
            username="customerstaff",
            password="testpass123",
        )

        BusinessMember.objects.create(
            business=self.business,
            user=staff,
            role=BusinessMember.ROLE_STAFF,
            is_active=True,
        )

        self.client.force_login(
            staff
        )

        response = self.client.post(
            reverse(
                "customers:archive",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.customer.refresh_from_db()

        self.assertTrue(
            self.customer.is_active
        )

    def test_staff_cannot_restore_customer(
        self,
    ):

        self.customer.is_active = False

        self.customer.save(
            update_fields=[
                "is_active",
            ]
        )

        staff = User.objects.create_user(
            username=(
                "customerstaffrestore"
            ),
            password="testpass123",
        )

        BusinessMember.objects.create(
            business=self.business,
            user=staff,
            role=BusinessMember.ROLE_STAFF,
            is_active=True,
        )

        self.client.force_login(
            staff
        )

        response = self.client.post(
            reverse(
                "customers:restore",
                args=[
                    self.customer.pk,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.customer.refresh_from_db()

        self.assertFalse(
            self.customer.is_active
        )

    def test_admin_can_archive_customer(
        self,
    ):

        admin = User.objects.create_user(
            username="customeradmin",
            password="testpass123",
        )

        BusinessMember.objects.create(
            business=self.business,
            user=admin,
            role=BusinessMember.ROLE_ADMIN,
            is_active=True,
        )

        self.client.force_login(
            admin
        )

        response = self.client.post(
            reverse(
                "customers:archive",
                args=[
                    self.customer.pk,
                ],
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
