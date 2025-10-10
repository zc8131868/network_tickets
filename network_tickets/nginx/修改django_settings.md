### 修改settings.py
```python
DEBUG = False

ALLOWED_HOSTS = ['django.netdevops.com']

CSRF_TRUSTED_ORIGINS = [
    "https://django.netdevops.com",
]

```