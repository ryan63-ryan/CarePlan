import os

SECRET_KEY = "dev-only-not-secure"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = ["core"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]

ROOT_URLCONF = "careplan_project.urls"
WSGI_APPLICATION = "careplan_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "careplan"),
        "USER": os.environ.get("POSTGRES_USER", "careplan"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "careplan"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
TEMPLATES = []

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
CAREPLAN_QUEUE = "careplan:pending"

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
