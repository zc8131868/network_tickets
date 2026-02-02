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
from auto_tickets.views.ip_deletion import ip_deletion
from auto_tickets.views.login import login_view, logout_view
from auto_tickets.views.get_pa_nat import get_pa_nat
from auto_tickets.views.auto_tickets_pa import auto_tickets_pa
from auto_tickets.views.auto_vpnnet import auto_vpnnet
from auto_tickets.views.ticket_management import ticket_management
from auto_tickets.views.ticket_detail_search import ticket_detail_search
from auto_tickets.views.ticket_analyzer import ticket_analyzer
from auto_tickets.views.serve_itsr_file import serve_itsr_file
from auto_tickets.views.itsr_auth import itsr_auth_page, itsr_auth_callback, itsr_check_auth, itsr_token_extractor, itsr_auth_sms_callback
from auto_tickets.views.mercury_chat import mercury_chat_view, mercury_chat_api
from auto_tickets.views.create_vendor_vpn_account import create_vendor_vpn_account
from auto_tickets.views.download_vpn_sample import download_vpn_sample
from auto_tickets.views.download_vpn_network_sample import download_vpn_network_sample
from auto_tickets.views.delete_vendor_vpn_account import delete_vendor_vpn_account
from auto_tickets.views.tickets_search import tickets_search
from auto_tickets.views.itsr_close_api import (
    create_close_session_api,
    submit_credentials_api,
    submit_sms_code_api,
    get_session_status_api,
    cancel_session_api,
    update_itsr_status_api
)





urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    # path('ipdb/', show_ipdb, name='show_ipdb'),
    path('ip_application/', ip_application, name='ip_application'),
    path('ip_deletion/', ip_deletion, name='ip_deletion'),
    path('single_split/', single_split, name='single_split'),
    path('multi_split/', multi_split, name='multi_split'),
    path('download_sample/', download_ITSRsample, name='download_sample'),
    path('accounts/login/', login_view, name='login'),
    path('accounts/logout/', logout_view, name='logout'),
    path('get_pa_nat/', get_pa_nat, name='get_pa_nat'),
    path('auto_tickets_pa/', auto_tickets_pa, name='auto_tickets_pa'),
    path('auto_vpnnet/', auto_vpnnet, name='auto_vpnnet'),
    path('ticket_management/', ticket_management, name='ticket_management'),
    path('ticket_detail_search/', ticket_detail_search, name='ticket_detail_search'),
    path('ticket_analyzer/', ticket_analyzer, name='ticket_analyzer'),
    path('itsr_files/<str:filename>', serve_itsr_file, name='serve_itsr_file'),
    path('itsr_auth_page/', itsr_auth_page, name='itsr_auth_page'),
    path('itsr_auth_callback/', itsr_auth_callback, name='itsr_auth_callback'),
    path('itsr_auth_sms_callback/', itsr_auth_sms_callback, name='itsr_auth_sms_callback'),
    path('itsr_check_auth/', itsr_check_auth, name='itsr_check_auth'),
    path('itsr_token_extractor/', itsr_token_extractor, name='itsr_token_extractor'),
    path('mercury_chat/', mercury_chat_view, name='mercury_chat'),
    path('mercury_chat_api/', mercury_chat_api, name='mercury_chat_api'),
    path('create_vendor_vpn_account/', create_vendor_vpn_account, name='create_vendor_vpn_account'),
    path('download_vpn_sample/', download_vpn_sample, name='download_vpn_sample'),
    path('download_vpn_network_sample/', download_vpn_network_sample, name='download_vpn_network_sample'),
    path('delete_vendor_vpn_account/', delete_vendor_vpn_account, name='delete_vendor_vpn_account'),
    path('tickets_search/', tickets_search, name='tickets_search'),
    # ITSR Close API endpoints
    path('api/itsr_close/create_session/', create_close_session_api, name='itsr_close_create_session'),
    path('api/itsr_close/submit_credentials/', submit_credentials_api, name='itsr_close_submit_credentials'),
    path('api/itsr_close/submit_sms/', submit_sms_code_api, name='itsr_close_submit_sms'),
    path('api/itsr_close/session_status/', get_session_status_api, name='itsr_close_session_status'),
    path('api/itsr_close/cancel_session/', cancel_session_api, name='itsr_close_cancel_session'),
    path('api/itsr_close/update_itsr_status/', update_itsr_status_api, name='itsr_close_update_itsr_status'),
]


# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
