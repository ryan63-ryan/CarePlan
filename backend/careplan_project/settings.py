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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/app/logs/careplan.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "standard",
        },
    },
    "loggers": {
        "careplan_project": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
