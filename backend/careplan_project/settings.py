import os

SECRET_KEY = "dev-only-not-secure"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = []
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]

ROOT_URLCONF = "careplan_project.urls"
WSGI_APPLICATION = "careplan_project.wsgi.application"

DATABASES = {}
TEMPLATES = []

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
