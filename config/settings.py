from pathlib import Path
import os
import sys

import dj_database_url
from dotenv import load_dotenv


# =========================================================
# BASE
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(
    BASE_DIR / ".env"
)


# =========================================================
# SECURITY
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-dev-key",
)

DEBUG = (
    os.getenv(
        "DEBUG",
        "True",
    ).lower()
    == "true"
)

IS_VERCEL = (
    os.getenv(
        "VERCEL",
        "",
    )
    == "1"
)

IS_TESTING = "test" in sys.argv


# =========================================================
# ALLOWED HOSTS
# =========================================================

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    ".vercel.app",
]

extra_hosts = os.getenv(
    "ALLOWED_HOSTS",
    "",
)

if extra_hosts:
    ALLOWED_HOSTS.extend(
        [
            host.strip()
            for host in extra_hosts.split(",")
            if host.strip()
        ]
    )


# =========================================================
# CSRF TRUSTED ORIGINS
# =========================================================

CSRF_TRUSTED_ORIGINS = [
    "https://*.vercel.app",
]

extra_csrf_origins = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "",
)

if extra_csrf_origins:
    CSRF_TRUSTED_ORIGINS.extend(
        [
            origin.strip()
            for origin in extra_csrf_origins.split(",")
            if origin.strip()
        ]
    )


# =========================================================
# APPLICATIONS
# =========================================================

INSTALLED_APPS = [

    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Cloudinary
    "cloudinary_storage",
    "cloudinary",

    # Project Apps
    "apps.core.apps.CoreConfig",
    "apps.customers.apps.CustomersConfig",
    "apps.businesses.apps.BusinessesConfig",
    "apps.products.apps.ProductsConfig",
    "apps.orders.apps.OrdersConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.notifications.apps.NotificationsConfig",
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URL / WSGI
# =========================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [
    {
        "BACKEND":
            "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                "apps.businesses.context_processors.current_business_context",
                "apps.notifications.context_processors.notification_context",
            ],
        },
    },
]


# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
)


if DATABASE_URL:

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=60,
            conn_health_checks=True,
        )
    }

else:

    DATABASES = {
        "default": {
            "ENGINE":
                "django.db.backends.postgresql",

            "NAME":
                os.getenv(
                    "DB_NAME",
                    "orderpilot_db",
                ),

            "USER":
                os.getenv(
                    "DB_USER",
                    "orderpilot_user",
                ),

            "PASSWORD":
                os.getenv(
                    "DB_PASSWORD",
                    "",
                ),

            "HOST":
                os.getenv(
                    "DB_HOST",
                    "localhost",
                ),

            "PORT":
                os.getenv(
                    "DB_PORT",
                    "5432",
                ),
        }
    }


# =========================================================
# PASSWORD VALIDATION
# =========================================================

AUTH_PASSWORD_VALIDATORS = [

    {
        "NAME":
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator",
    },

    {
        "NAME":
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator",
    },

    {
        "NAME":
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator",
    },

    {
        "NAME":
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator",
    },
]


# =========================================================
# INTERNATIONALIZATION
# =========================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Dhaka"

USE_I18N = True

USE_TZ = True


# =========================================================
# STATIC FILES
# =========================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = (
    BASE_DIR
    / "staticfiles"
)


# =========================================================
# MEDIA / CLOUDINARY
# =========================================================

MEDIA_URL = "/media/"

CLOUDINARY_URL = os.getenv(
    "CLOUDINARY_URL",
)


# ---------------------------------------------------------
# Static files storage
# ---------------------------------------------------------
# Development and tests should not depend on a collectstatic
# manifest. Production uses WhiteNoise's compressed manifest
# storage for cache-busted static assets.

if DEBUG or IS_TESTING:
    STATICFILES_BACKEND = (
        "django.contrib.staticfiles.storage."
        "StaticFilesStorage"
    )
else:
    STATICFILES_BACKEND = (
        "whitenoise.storage."
        "CompressedManifestStaticFilesStorage"
    )


# ---------------------------------------------------------
# Media storage
# ---------------------------------------------------------

if CLOUDINARY_URL:

    STORAGES = {

        "default": {
            "BACKEND":
                "cloudinary_storage.storage."
                "MediaCloudinaryStorage",
        },

        "staticfiles": {
            "BACKEND":
                STATICFILES_BACKEND,
        },
    }

else:

    MEDIA_ROOT = (
        BASE_DIR
        / "media"
    )

    STORAGES = {

        "default": {
            "BACKEND":
                "django.core.files.storage."
                "FileSystemStorage",
        },

        "staticfiles": {
            "BACKEND":
                STATICFILES_BACKEND,
        },
    }

# =========================================================
# AUTH
# =========================================================

LOGIN_URL = "/login/"

LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = "/login/"


# =========================================================
# EMAIL
# =========================================================

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    "OrderPilot <noreply@orderpilot.local>",
)


# =========================================================
# DEFAULT PRIMARY KEY
# =========================================================

DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)


# =========================================================
# PRODUCTION SECURITY
# =========================================================

if IS_VERCEL or not DEBUG:

    SESSION_COOKIE_SECURE = True

    CSRF_COOKIE_SECURE = True

    SECURE_SSL_REDIRECT = True

    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    SECURE_CONTENT_TYPE_NOSNIFF = True

    X_FRAME_OPTIONS = "DENY"

    SECURE_REFERRER_POLICY = "same-origin"


# =========================================================
# HSTS
# =========================================================

if IS_VERCEL:

    SECURE_HSTS_SECONDS = 3600

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    SECURE_HSTS_PRELOAD = False