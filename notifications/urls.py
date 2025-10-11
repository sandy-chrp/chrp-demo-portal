# notifications/urls.py

from django.urls import path
from . import views, api_views, admin_api_views, admin_views

urlpatterns = [
    # Customer notification pages
    path('', views.notification_list_view, name='list'),
    
    # Customer API endpoints
    path('api/unread-count/', api_views.get_unread_count_api, name='api_unread_count'),
    path('api/list/', api_views.get_notifications_api, name='api_notification_list'),
    path('api/<int:notification_id>/read/', api_views.mark_as_read_api, name='api_mark_as_read'),
    path('api/mark-all-read/', api_views.mark_all_as_read_api, name='api_mark_all_as_read'),
    path('api/<int:notification_id>/delete/', api_views.delete_notification_api, name='api_delete_notification'),
    
    # Admin notification pages
    path('admin/', admin_views.admin_notification_center, name='admin_notifications'),
    path('admin/preferences/', admin_views.admin_notification_preferences, name='admin_notification_preferences'),
    path('admin/send-bulk/', admin_views.admin_send_bulk_notification, name='admin_send_bulk'),
    
    # Admin API endpoints
    path('api/admin/unread-count/', admin_api_views.admin_unread_count, name='api_admin_unread_count'),
    path('api/admin/list/', admin_api_views.admin_notification_list, name='api_admin_notification_list'),
    path('api/admin/<int:notification_id>/read/', admin_api_views.admin_mark_as_read, name='api_admin_mark_as_read'),
    path('api/admin/mark-all-read/', admin_api_views.admin_mark_all_as_read, name='api_admin_mark_all_as_read'), 
    path('api/admin/<int:notification_id>/delete/', admin_api_views.admin_delete_notification, name='api_admin_delete_notification'), 
]