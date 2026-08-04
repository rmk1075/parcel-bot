# 데모용 최소 설정 — DB·미들웨어 없음(CSRF 미들웨어가 없어 POST에 csrf_exempt 불필요)
SECRET_KEY = "demo-only-not-secret"
DEBUG = True
ALLOWED_HOSTS = ["*"]
ROOT_URLCONF = "parcel_bot.urls"
INSTALLED_APPS = []
MIDDLEWARE = []
DATABASES = {}
USE_TZ = True
