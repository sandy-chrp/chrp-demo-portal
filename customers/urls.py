# customers/urls.py - Complete URL Configuration

from django.urls import path,re_path
from . import views
from . import liked_demos_views

app_name = 'customers'

urlpatterns = [
    # Dashboard
    path('', views.customer_dashboard, name='dashboard'),
    
    # Demo Section
    path('demos/', views.browse_demos, name='browse_demos'),
    path('demos/<slug:slug>/', views.demo_detail, name='demo_detail'),
    
    # ✅ NEW: WebGL 3D Viewer - Separate route for WebGL demos
    path('demos/<slug:slug>/view-3d/', views.webgl_viewer, name='webgl_viewer'),
    
    # ✅ NEW: Serve WebGL files directly (without template processing)
    re_path(
        r'^demos/(?P<slug>[\w-]+)/webgl-content/(?P<filepath>.+)$',
        views.serve_webgl_file,
        name='serve_webgl_file'
    ),
    
    path('request-demo/', views.request_demo, name='request_demo'),
    path('my-requests/', views.demo_requests, name='demo_requests'),
    
    # Business Enquiries
    path('enquiries/', views.enquiries, name='enquiries'),
    path('send-enquiry/', views.send_enquiry, name='send_enquiry'),
    path('contact-sales/', views.contact_sales, name='contact_sales'),
    
    # Liked Demos
    path('liked-demos/', liked_demos_views.liked_demos, name='liked_demos'),

    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    
    # AJAX Endpoints
    path('ajax/demo/<int:demo_id>/like/', views.toggle_demo_like, name='toggle_demo_like'),
    path('ajax/demo/<int:demo_id>/feedback/', views.submit_demo_feedback, name='submit_demo_feedback'),
    path('ajax/notification/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('ajax/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # NEW AJAX ENDPOINTS
    path('ajax/subcategories/<int:category_id>/', views.ajax_subcategories, name='ajax_subcategories'),
    path('ajax/demos/', views.ajax_demos_by_category, name='ajax_demos_by_category'),
    path('ajax/demo/<int:demo_id>/', views.ajax_demo_detail, name='ajax_demo_detail'),
    path('ajax/demo-request/<int:request_id>/cancel/', views.cancel_demo_request, name='cancel_demo_request'),
    path('ajax/check-slot-availability/', views.ajax_check_slot_availability, name='check_slot_availability'),
    path('ajax/booking-calendar/', views.ajax_get_booking_calendar, name='booking_calendar'),

        # Security violation logging
    path('ajax/log-security-violation/', 
         views.log_security_violation, 
         name='log_security_violation'),
    

  

]