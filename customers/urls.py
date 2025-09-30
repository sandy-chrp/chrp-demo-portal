# customers/urls.py - Fixed Version
from django.urls import path
from . import views

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
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('ajax/notification/<int:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    path('ajax/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    
    # AJAX Endpoints - Fixed URLs
    path('ajax/demo/<int:demo_id>/like/', views.toggle_demo_like, name='toggle_demo_like'),
    path('ajax/demo/<int:demo_id>/feedback/', views.submit_demo_feedback, name='submit_demo_feedback'),
    path('ajax/demo-request/<int:request_id>/cancel/', views.cancel_demo_request, name='cancel_demo_request'),
    # customers/urls.py

]