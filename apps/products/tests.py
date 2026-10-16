from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import (
    Business,
    BusinessMember,
)

from .models import (
    Product,
    StockAdjustment,
)


User = get_user_model()


class ProductModuleTests(TestCase):
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

        self.product = Product.objects.create(
            business=self.business,
            name="Premium Face Serum",
            sku="SERUM-001",
            selling_price="1200.00",
            cost_price="750.00",
            stock_quantity=25,
            low_stock_threshold=5,
            is_active=True,
        )

        self.other_product = Product.objects.create(
            business=self.other_business,
            name="Other Product",
            sku="OTHER-001",
            selling_price="800.00",
            cost_price="500.00",
            stock_quantity=10,
            low_stock_threshold=3,
            is_active=True,
        )

        self.client.login(
            username="owner1",
            password="testpass123",
        )

    def test_product_list_only_shows_current_business_products(self):
        response = self.client.get(
            reverse("products:list")
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Premium Face Serum",
        )

        self.assertNotContains(
            response,
            "Other Product",
        )

    def test_user_cannot_view_other_business_product(self):
        response = self.client.get(
            reverse(
                "products:detail",
                args=[self.other_product.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_user_cannot_edit_other_business_product(self):
        response = self.client.get(
            reverse(
                "products:update",
                args=[self.other_product.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            404,
        )

    def test_product_creation_assigns_current_business(self):
        response = self.client.post(
            reverse("products:create"),
            {
                "name": "Vitamin C Cleanser",
                "sku": "CLEAN-001",
                "selling_price": "850.00",
                "cost_price": "500.00",
                "stock_quantity": 8,
                "low_stock_threshold": 3,
                "description": "",
                "is_active": "on",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        product = Product.objects.get(
            sku="CLEAN-001"
        )

        self.assertEqual(
            product.business,
            self.business,
        )

    def test_product_update_works_for_current_business(self):
        response = self.client.post(
            reverse(
                "products:update",
                args=[self.product.pk],
            ),
            {
                "name": "Premium Serum Updated",
                "sku": "SERUM-001",
                "selling_price": "1300.00",
                "cost_price": "750.00",
                "stock_quantity": 20,
                "low_stock_threshold": 5,
                "description": "",
                "is_active": "on",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.name,
            "Premium Serum Updated",
        )

        self.assertEqual(
            str(self.product.selling_price),
            "1300.00",
        )

    def test_archive_product(self):
        response = self.client.post(
            reverse(
                "products:archive",
                args=[self.product.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertFalse(
            self.product.is_active
        )

    def test_restore_product(self):
        self.product.is_active = False
        self.product.save()

        response = self.client.post(
            reverse(
                "products:restore",
                args=[self.product.pk],
            )
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertTrue(
            self.product.is_active
        )

    def test_same_business_cannot_use_duplicate_non_empty_sku(self):
        response = self.client.post(
            reverse("products:create"),
            {
                "name": "Duplicate Serum",
                "sku": "SERUM-001",
                "selling_price": "999.00",
                "cost_price": "600.00",
                "stock_quantity": 5,
                "low_stock_threshold": 2,
                "description": "",
                "is_active": "on",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            Product.objects.filter(
                business=self.business,
                sku="SERUM-001",
            ).count(),
            1,
        )

    def test_different_business_can_use_same_sku(self):
        product = Product.objects.create(
            business=self.other_business,
            name="Other Serum",
            sku="SERUM-001",
            selling_price="1000.00",
            cost_price="700.00",
            stock_quantity=5,
            low_stock_threshold=2,
            is_active=True,
        )

        self.assertEqual(
            product.sku,
            "SERUM-001",
        )

        self.assertEqual(
            product.business,
            self.other_business,
        )

    def test_low_stock_property(self):
        self.product.stock_quantity = 5
        self.product.low_stock_threshold = 5

        self.assertTrue(
            self.product.is_low_stock
        )

    def test_healthy_stock_property(self):
        self.product.stock_quantity = 10
        self.product.low_stock_threshold = 5

        self.assertFalse(
            self.product.is_low_stock
        )

    def test_product_pages_require_login(self):
        self.client.logout()

        response = self.client.get(
            reverse("products:list")
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        # =========================================================
    # STOCK ADJUSTMENT TESTS
    # =========================================================

    def test_product_creation_records_opening_stock(
        self,
    ):

        response = self.client.post(
            reverse(
                "products:create"
            ),
            {
                "name":
                    "Opening Stock Product",

                "sku":
                    "OPEN-001",

                "selling_price":
                    "500.00",

                "cost_price":
                    "300.00",

                "stock_quantity":
                    12,

                "low_stock_threshold":
                    3,

                "description":
                    "",

                "is_active":
                    "on",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        product = (
            Product.objects.get(
                business=self.business,
                sku="OPEN-001",
            )
        )

        adjustment = (
            StockAdjustment.objects.get(
                product=product
            )
        )

        self.assertEqual(
            adjustment.adjustment_type,
            StockAdjustment.TYPE_OPENING,
        )

        self.assertEqual(
            adjustment.quantity,
            12,
        )

        self.assertEqual(
            adjustment.before_quantity,
            0,
        )

        self.assertEqual(
            adjustment.after_quantity,
            12,
        )

        self.assertEqual(
            adjustment.adjusted_by,
            self.user,
        )

    def test_restock_increases_stock_and_creates_history(
        self,
    ):

        response = self.client.post(
            reverse(
                "products:stock_adjust",
                args=[
                    self.product.pk
                ],
            ),
            {
                "adjustment_type":
                    StockAdjustment.TYPE_RESTOCK,

                "quantity":
                    10,

                "note":
                    "Supplier restock",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            35,
        )

        adjustment = (
            StockAdjustment.objects
            .filter(
                product=self.product
            )
            .latest("id")
        )

        self.assertEqual(
            adjustment.before_quantity,
            25,
        )

        self.assertEqual(
            adjustment.after_quantity,
            35,
        )

        self.assertEqual(
            adjustment.quantity,
            10,
        )

        self.assertEqual(
            adjustment.note,
            "Supplier restock",
        )

        self.assertEqual(
            adjustment.adjusted_by,
            self.user,
        )

    def test_damaged_stock_decreases_inventory(
        self,
    ):

        response = self.client.post(
            reverse(
                "products:stock_adjust",
                args=[
                    self.product.pk
                ],
            ),
            {
                "adjustment_type":
                    StockAdjustment.TYPE_DAMAGED,

                "quantity":
                    5,

                "note":
                    "Damaged items",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            20,
        )

        adjustment = (
            StockAdjustment.objects
            .filter(
                product=self.product
            )
            .latest("id")
        )

        self.assertEqual(
            adjustment.before_quantity,
            25,
        )

        self.assertEqual(
            adjustment.after_quantity,
            20,
        )

    def test_stock_cannot_be_reduced_below_zero(
        self,
    ):

        response = self.client.post(
            reverse(
                "products:stock_adjust",
                args=[
                    self.product.pk
                ],
            ),
            {
                "adjustment_type":
                    StockAdjustment.TYPE_LOST,

                "quantity":
                    100,

                "note":
                    "Invalid adjustment",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            25,
        )

        self.assertFalse(
            StockAdjustment.objects.filter(
                product=self.product,
                adjustment_type=(
                    StockAdjustment.TYPE_LOST
                ),
            ).exists()
        )

    def test_stock_adjustment_requires_positive_quantity(
        self,
    ):

        response = self.client.post(
            reverse(
                "products:stock_adjust",
                args=[
                    self.product.pk
                ],
            ),
            {
                "adjustment_type":
                    StockAdjustment.TYPE_RESTOCK,

                "quantity":
                    0,

                "note":
                    "",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            25,
        )

        self.assertFalse(
            StockAdjustment.objects.filter(
                product=self.product
            ).exists()
        )

    def test_user_cannot_adjust_other_business_stock(
        self,
    ):

        response = self.client.post(
            reverse(
                "products:stock_adjust",
                args=[
                    self.other_product.pk
                ],
            ),
            {
                "adjustment_type":
                    StockAdjustment.TYPE_RESTOCK,

                "quantity":
                    10,

                "note":
                    "Should fail",
            },
        )

        self.assertEqual(
            response.status_code,
            404,
        )

        self.other_product.refresh_from_db()

        self.assertEqual(
            self.other_product.stock_quantity,
            10,
        )

    def test_product_update_cannot_directly_change_stock(
        self,
    ):

        response = self.client.post(
            reverse(
                "products:update",
                args=[
                    self.product.pk
                ],
            ),
            {
                "name":
                    self.product.name,

                "sku":
                    self.product.sku,

                "selling_price":
                    str(
                        self.product.selling_price
                    ),

                "cost_price":
                    str(
                        self.product.cost_price
                    ),

                # Malicious direct stock change.
                "stock_quantity":
                    999,

                "low_stock_threshold":
                    self.product.low_stock_threshold,

                "description":
                    self.product.description,

                "is_active":
                    "on",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            25,
        )

        # =========================================================
    # PRODUCT LIST SEARCH / FILTER / PAGINATION TESTS
    # =========================================================

    def test_product_list_search_by_name(
        self,
    ):

        response = self.client.get(
            reverse("products:list"),
            {
                "q": "Premium Face Serum",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.product.name,
        )


    def test_product_list_search_by_sku(
        self,
    ):

        response = self.client.get(
            reverse("products:list"),
            {
                "q": self.product.sku,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.product.name,
        )


    def test_product_list_filters_archived_products(
        self,
    ):

        self.product.is_active = False

        self.product.save(
            update_fields=[
                "is_active",
            ]
        )

        response = self.client.get(
            reverse("products:list"),
            {
                "status": "inactive",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.product.name,
        )


    def test_product_list_all_status_shows_active_and_inactive(
        self,
    ):

        archived_product = Product.objects.create(
            business=self.business,
            name="Archived Product",
            sku="ARCH-001",
            selling_price="500.00",
            cost_price="300.00",
            stock_quantity=5,
            low_stock_threshold=2,
            is_active=False,
        )

        response = self.client.get(
            reverse("products:list"),
            {
                "status": "all",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.product.name,
        )

        self.assertContains(
            response,
            archived_product.name,
        )


    def test_product_list_filters_low_stock(
        self,
    ):

        self.product.stock_quantity = 3

        self.product.low_stock_threshold = 5

        self.product.save(
            update_fields=[
                "stock_quantity",
                "low_stock_threshold",
            ]
        )

        response = self.client.get(
            reverse("products:list"),
            {
                "stock": "low",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.product.name,
        )


    def test_product_list_filters_out_of_stock(
        self,
    ):

        self.product.stock_quantity = 0

        self.product.save(
            update_fields=[
                "stock_quantity",
            ]
        )

        response = self.client.get(
            reverse("products:list"),
            {
                "stock": "out",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.product.name,
        )


    def test_product_list_paginates_results(
        self,
    ):

        for index in range(15):

            Product.objects.create(
                business=self.business,
                name=f"Product {index}",
                sku=f"PROD-{index:03d}",
                selling_price="500.00",
                cost_price="300.00",
                stock_quantity=10,
                low_stock_threshold=2,
                is_active=True,
            )

        response = self.client.get(
            reverse("products:list")
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
                    "products"
                ]
            ),
            10,
        )

        self.assertTrue(
            page_obj.has_next()
        )


    def test_product_filter_query_preserves_values(
        self,
    ):

        response = self.client.get(
            reverse("products:list"),
            {
                "q": "Serum",
                "status": "all",
                "stock": "low",
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
            "q=Serum",
            filter_query,
        )

        self.assertIn(
            "status=all",
            filter_query,
        )

        self.assertIn(
            "stock=low",
            filter_query,
        )

        self.assertNotIn(
            "page=",
            filter_query,
        )


    def test_product_search_respects_business_isolation(
        self,
    ):

        response = self.client.get(
            reverse("products:list"),
            {
                "q":
                    self.other_product.name,

                "status":
                    "all",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        products = (
            response.context[
                "products"
            ]
        )

        self.assertNotIn(
            self.other_product,
            products,
        )

        self.assertEqual(
            len(products),
            0,
        )

        # =========================================================
    # PRODUCT ROLE / PERMISSION TESTS
    # =========================================================

    def test_staff_cannot_adjust_stock(
        self,
    ):

        staff = User.objects.create_user(
            username="productstaff",
            password="testpass123",
        )

        BusinessMember.objects.create(
            business=self.business,
            user=staff,
            role=BusinessMember.ROLE_STAFF,
            is_active=True,
        )

        original_stock = (
            self.product.stock_quantity
        )

        self.client.force_login(
            staff
        )

        response = self.client.post(
            reverse(
                "products:stock_adjust",
                args=[
                    self.product.pk,
                ],
            ),
            {
                "adjustment_type":
                    "restock",

                "quantity":
                    5,

                "note":
                    "Staff should not adjust.",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            original_stock,
        )

    def test_staff_cannot_archive_product(
        self,
    ):

        staff = User.objects.create_user(
            username="productstaffarchive",
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
                "products:archive",
                args=[
                    self.product.pk,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.product.refresh_from_db()

        self.assertTrue(
            self.product.is_active
        )

    def test_staff_cannot_restore_product(
        self,
    ):

        self.product.is_active = False

        self.product.save(
            update_fields=[
                "is_active",
            ]
        )

        staff = User.objects.create_user(
            username="productstaffrestore",
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
                "products:restore",
                args=[
                    self.product.pk,
                ],
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.product.refresh_from_db()

        self.assertFalse(
            self.product.is_active
        )

    def test_admin_can_adjust_stock(
        self,
    ):

        admin = User.objects.create_user(
            username="productadmin",
            password="testpass123",
        )

        BusinessMember.objects.create(
            business=self.business,
            user=admin,
            role=BusinessMember.ROLE_ADMIN,
            is_active=True,
        )

        original_stock = (
            self.product.stock_quantity
        )

        self.client.force_login(
            admin
        )

        response = self.client.post(
            reverse(
                "products:stock_adjust",
                args=[
                    self.product.pk,
                ],
            ),
            {
                "adjustment_type":
                    "restock",

                "quantity":
                    5,

                "note":
                    "Admin restock.",
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.product.refresh_from_db()

        self.assertEqual(
            self.product.stock_quantity,
            original_stock + 5,
        )
