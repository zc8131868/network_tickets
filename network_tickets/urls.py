"""
URL configuration for network_tickets project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from views.index import index
from auto_tickets.views.qyt_department_view_summary import show_ipdb
from auto_tickets.views.qyt_department_addstudent import single_split
from auto_tickets.views.multi_split import multi_split
from auto_tickets.views.download_ITSRsample import download_ITSRsample
from auto_tickets.views.ip_application import ip_application






urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    # path('ipdb/', show_ipdb, name='show_ipdb'),
    path('ip_application/', ip_application, name='ip_application'),
    path('single_split/', single_split, name='single_split'),
    path('multi_split/', multi_split, name='multi_split'),
    path('download_sample/', download_ITSRsample, name='download_sample'),
]


# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
