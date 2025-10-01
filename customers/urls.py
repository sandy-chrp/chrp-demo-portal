# customers/urls.py - Complete with AJAX endpoints
from django.urls import path
from . import views
from . import liked_demos_views  # ✅ ADD THIS IMPORT


app_name = 'customers'

urlpatterns = [
    # Dashboard
    path('', views.customer_dashboard, name='dashboard'),
    
    # Demo Section
    path('demos/', views.browse_demos, name='browse_demos'),
    path('demos/<slug:slug>/', views.demo_detail, name='demo_detail'),
    path('request-demo/', views.request_demo, name='request_demo'),
    path('my-requests/', views.demo_requests, name='demo_requests'),
    
    # Business Enquiries
    path('enquiries/', views.enquiries, name='enquiries'),
    path('send-enquiry/', views.send_enquiry, name='send_enquiry'),
    path('contact-sales/', views.contact_sales, name='contact_sales'),
    path('liked-demos/', liked_demos_views.liked_demos, name='liked_demos'),

    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    
    # AJAX Endpoints - FIXED PATHS
    path('ajax/demo/<int:demo_id>/like/', views.toggle_demo_like, name='toggle_demo_like'),
    path('ajax/demo/<int:demo_id>/feedback/', views.submit_demo_feedback, name='submit_demo_feedback'),
    path('ajax/demo-request/<int:request_id>/cancel/', views.cancel_demo_request, name='cancel_demo_request'),
    path('ajax/notification/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('ajax/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # NEW AJAX ENDPOINTS FOR REQUEST DEMO
    path('ajax/subcategories/<int:category_id>/', views.ajax_subcategories, name='ajax_subcategories'),
    path('ajax/demos/', views.ajax_demos_by_category, name='ajax_demos_by_category'),
    path('ajax/demo/<int:demo_id>/', views.ajax_demo_detail, name='ajax_demo_detail'),
]