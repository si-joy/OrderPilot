from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.businesses.models import Business, BusinessMember

from .models import Product


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