"""
Django settings for core project.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-w^tjfe4-!!n+%$+0lh_l#_nzahcd1f^5h&cpg(u#ph9x@5i&e&'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app',  # <-- Tu aplicación conectada
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # <-- Conexión a tu carpeta de HTML
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'app.contexto.panel',  # menú activo y usuario del panel
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Base de datos: SQL Server (paquete mssql-django)
# Por defecto usa la base NapoBeauty en este equipo con autenticación de Windows.
# Si alguien del equipo usa otro servidor o el usuario 'sa', puede definir estas
# variables de entorno en su PC sin tocar este archivo:
#   DB_HOST, DB_NAME, DB_USER, DB_PASSWORD
# (si DB_USER queda vacío se usa la autenticación de Windows).
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': os.environ.get('DB_NAME', 'NapoBeauty'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': '',
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'OPTIONS': {
            # Driver de Microsoft para Python: trae su propio controlador ODBC
            'python_driver': 'mssql_python',
            # El certificado del SQL Server local no es de confianza: solo para desarrollo
            'extra_params': 'Encrypt=yes;TrustServerCertificate=yes',
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'es-ni'  # <-- Español de Nicaragua
TIME_ZONE = 'America/Managua' # <-- Zona horaria local
USE_I18N = True
# Las fechas se guardan en hora local de Managua, igual que los valores por defecto
# de SQL Server (SYSDATETIME()). Con True, Django las guardaría en UTC (6 horas de
# diferencia) y los reportes por día se descuadrarían.
USE_TZ = False

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static'] # <-- Conexión a tu carpeta de CSS/JS/Logos

# Configuraciones para las fotos de maquillaje
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Email
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}
# Datos de la tienda que salen en el recibo de compra (ventas/<id>/recibo/).
# Cámbialos por los datos reales de Napo Beauty.
NAPO_TIENDA = {
    'nombre': 'Napo Beauty',
    'ruc': 'J0310000123456',
    'direccion': 'Managua, Nicaragua',
    'telefono': '+505 8888-9999',
    'correo': 'admin@napobeauty.com',
    'mensaje': '¡Gracias por tu compra! Cambios y devoluciones dentro de los 15 días presentando este recibo.',
}
