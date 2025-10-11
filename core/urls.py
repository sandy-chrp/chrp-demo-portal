# core/urls.py - UPDATED WITH WEBGL SUPPORT

from django.urls import path
from . import views
from core import category_views
from . import demo_request_views
from . import admin_customer_views
from . import business_categories_views
from . import admin_notification_views
from . import admin_settings_views
from .views import get_subcategories_ajax, get_subcategories_for_category
from . import user_activity_analytics_views

# Import WebGL views
from . import webgl_views

app_name = 'core'

urlpatterns = [
    # =====================================
    # CUSTOMER PORTAL URLs
    # =====================================
    
    # Landing Page & Home
    # path('', views.landing_page_view, name='home'),

    path('contact/', views.contact_view, name='contact'),
    path('contact-sales/', views.contact_sales_view, name='contact_sales'),
    
    # =====================================
    # ADMIN AUTHENTICATION
    # =====================================
    
    # Admin Authentication
    path('', views.admin_login_view, name='admin_login'),
    path('admin/logout/', views.admin_logout_view, name='admin_logout'),
    path('admin/dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    
    # path('dashboard/', views.dashboard_redirect, name='dashboard'),

    # =====================================
    # ADMIN CUSTOMER MANAGEMENT (CRUD)
    # =====================================
    
    path('admin/customers/', admin_customer_views.admin_customers_list, name='admin_users'),
    path('admin/customers/create/', admin_customer_views.admin_create_customer, name='admin_create_customer'),
    path('admin/customers/export/', admin_customer_views.admin_customer_export_view, name='admin_customer_export'),
    path('admin/customers/<int:customer_id>/', admin_customer_views.admin_customer_detail, name='admin_customer_detail'),
    path('admin/customers/<int:customer_id>/edit/', admin_customer_views.admin_edit_customer, name='admin_edit_customer'),
    path('admin/customers/<int:customer_id>/approve/', admin_customer_views.admin_approve_customer, name='admin_approve_customer'),
    path('admin/customers/<int:customer_id>/block/', admin_customer_views.admin_block_customer, name='admin_block_customer'),
    path('admin/customers/<int:customer_id>/unblock/', admin_customer_views.admin_unblock_customer, name='admin_unblock_customer'),
    path('admin/customers/<int:customer_id>/delete/', admin_customer_views.admin_delete_customer, name='admin_delete_customer'),
    path('admin/customers/bulk-actions/', admin_customer_views.admin_bulk_customer_actions, name='admin_bulk_customer_actions'),
    path('admin/customers/bulk-import/', admin_customer_views.admin_bulk_import_customers, name='admin_bulk_import_customers'),
    path('admin/customers/import-template/', admin_customer_views.download_import_template, name='download_import_template'),

    # =====================================
    # ADMIN DEMO MANAGEMENT  
    # =====================================
    
    # Demo List & Management
    path('admin/demos/', views.admin_demos_view, name='admin_demos'),
    path('admin/demos/add/', views.admin_add_demo_view, name='admin_add_demo'),
    path('admin/demos/stats/', views.admin_demo_stats_view, name='admin_demo_stats'),
    path('admin/demos/bulk-actions/', views.admin_bulk_demo_actions_view, name='admin_bulk_demo_actions'),
    
    # Individual Demo Operations
    path('admin/demos/<int:demo_id>/', views.admin_demo_detail_view, name='admin_demo_detail'),
    path('admin/demos/<int:demo_id>/watch/', views.admin_demo_watch_view, name='admin_demo_watch'),
    path('admin/demos/<int:demo_id>/delete/', views.admin_delete_demo_view, name='admin_delete_demo'),
    path('admin/demos/<int:demo_id>/toggle-status/', views.admin_toggle_demo_status_view, name='admin_toggle_demo_status'),
    path('admin/demos/filter/', demo_request_views.admin_get_filtered_demos, name='admin_filter_demos'),

    # =====================================
    # WEBGL DEMO VIEWING & SERVING (NEW)
    # =====================================
    
    # Admin WebGL Preview Routes
    path('admin/webgl-preview/<int:demo_id>/', webgl_views.admin_webgl_preview, name='admin_webgl_preview'),
    path('admin/universal-preview/<int:demo_id>/', webgl_views.admin_universal_preview, name='admin_universal_preview'),
    
    # Customer Universal Viewer
    path('demo/view/<int:demo_id>/', webgl_views.universal_viewer, name='universal_viewer'),
    
    # WebGL Content Serving
    path('webgl/serve/<int:demo_id>/', webgl_views.serve_webgl_content, name='serve_webgl_content'),
    path('api/webgl-asset/<int:demo_id>/<path:asset_path>/', webgl_views.serve_webgl_asset, name='serve_webgl_asset'),
    
    # WebGL Debug/Info (Admin Only)
    path('admin/webgl-info/<int:demo_id>/', webgl_views.webgl_file_info, name='webgl_file_info'),

    # =====================================
    # ADMIN ENQUIRY MANAGEMENT
    # =====================================
    
    path('admin/enquiries/', views.admin_enquiries_view, name='admin_enquiries'),
    path('admin/enquiries/<int:enquiry_id>/', views.admin_enquiry_detail_view, name='admin_enquiry_detail'),
    path('admin/enquiries/<int:enquiry_id>/respond/', views.admin_respond_enquiry_view, name='admin_respond_enquiry'),
    path('admin/enquiries/<int:enquiry_id>/delete/', views.admin_delete_enquiry_view, name='admin_delete_enquiry'),
    path('admin/enquiries/<int:enquiry_id>/assign/', views.admin_assign_enquiry_view, name='admin_assign_enquiry'),
    path('admin/enquiries/<int:enquiry_id>/update-priority/', views.admin_update_enquiry_priority_view, name='admin_update_enquiry_priority'),
    path('admin/enquiries/export/', views.admin_export_enquiries_view, name='admin_export_enquiries'),
        
    # =====================================
    # ADMIN DEMO REQUEST MANAGEMENT
    # =====================================
    
    path('admin/demo-requests/', demo_request_views.admin_demo_requests_list_view, name='admin_demo_requests'),
    path('admin/demo-requests/create/', demo_request_views.admin_create_demo_request_view, name='admin_create_demo_request'),
    path('admin/demo-requests/calendar/', demo_request_views.admin_demo_requests_calendar_view, name='admin_demo_requests_calendar'),
    path('admin/demo-requests/bulk-actions/', demo_request_views.admin_bulk_demo_request_actions_view, name='admin_bulk_demo_request_actions'),
    
    # Individual Demo Request Operations
    path('admin/demo-requests/<int:request_id>/', demo_request_views.admin_demo_request_detail_view, name='admin_demo_request_detail'),
    path('admin/demo-requests/<int:request_id>/edit/', demo_request_views.admin_edit_demo_request_view, name='admin_edit_demo_request'),
    path('admin/demo-requests/<int:request_id>/delete/', demo_request_views.admin_delete_demo_request_view, name='admin_delete_demo_request'),
    path('admin/demo-requests/<int:request_id>/confirm/', demo_request_views.admin_confirm_demo_request_view, name='admin_confirm_demo_request'),
    path('admin/demo-requests/ajax-check-slots/', demo_request_views.ajax_admin_check_slot_availability, name='ajax_admin_check_slot_availability'),
    
    # =====================================
    # ADMIN CATEGORY MANAGEMENT
    # =====================================
    
    # Category List & Management
    path('admin/categories/', category_views.admin_categories_view, name='admin_categories'),
    path('admin/categories/add/', category_views.admin_add_category_view, name='admin_add_category'),
    path('admin/categories/export/', category_views.admin_category_export_view, name='admin_category_export'),
    path('admin/categories/stats/', category_views.admin_category_stats_view, name='admin_category_stats'),
    path('admin/categories/bulk-actions/', category_views.admin_bulk_category_actions_view, name='admin_bulk_category_actions'),
    path('admin/categories/reorder/', category_views.admin_reorder_categories_view, name='admin_reorder_categories'),
    path('api/subcategories/', get_subcategories_ajax, name='get_subcategories_ajax'),
    path('auth/ajax/get-subcategories/', get_subcategories_for_category, name='get_subcategories'),

    # Business Category Management
    path('admin/business-categories/', business_categories_views.admin_business_categories, name='admin_business_categories'),
    path('admin/business-categories/create/', business_categories_views.admin_business_category_create, name='admin_business_category_create'),
    path('admin/business-categories/<int:category_id>/edit/', business_categories_views.admin_business_category_edit, name='admin_business_category_edit'),
    path('admin/business-categories/<int:category_id>/delete/', business_categories_views.admin_business_category_delete, name='admin_business_category_delete'),
    path('admin/business-categories/<int:category_id>/toggle-status/', business_categories_views.admin_business_category_toggle_status, name='admin_business_category_toggle_status'),
    
    # Business Subcategory Management
    path('admin/business-subcategories/', business_categories_views.admin_business_subcategories, name='admin_business_subcategories'),
    path('admin/business-subcategories/create/', business_categories_views.admin_business_subcategory_create, name='admin_business_subcategory_create'),
    path('admin/business-subcategories/<int:subcategory_id>/edit/', business_categories_views.admin_business_subcategory_edit, name='admin_business_subcategory_edit'),
    path('admin/business-subcategories/<int:subcategory_id>/delete/', business_categories_views.admin_business_subcategory_delete, name='admin_business_subcategory_delete'),
    path('admin/business-subcategories/<int:subcategory_id>/toggle-status/', business_categories_views.admin_business_subcategory_toggle_status, name='admin_business_subcategory_toggle_status'),

    
    # Individual Category Operations
    path('admin/categories/<int:category_id>/', category_views.admin_category_detail_view, name='admin_category_detail'),
    path('admin/categories/<int:category_id>/edit/', category_views.admin_edit_category_view, name='admin_edit_category'),
    path('admin/categories/<int:category_id>/delete/', category_views.admin_delete_category_view, name='admin_delete_category'),
    path('admin/categories/<int:category_id>/toggle-status/', category_views.admin_toggle_category_status_view, name='admin_toggle_category_status'),
    path('admin/categories/<int:category_id>/duplicate/', category_views.admin_category_duplicate_view, name='admin_duplicate_category'),
    
    # =====================================
    # ADMIN SETTINGS & SYSTEM
    # =====================================
    
    # Main Settings Dashboard
    path('admin/settings/', admin_settings_views.admin_settings_view, name='admin_settings'),
    # Site Configuration
    path('admin/settings/site/', admin_settings_views.admin_site_settings_view, name='admin_site_settings'),
    # Demo Settings
    path('admin/settings/demo/', admin_settings_views.admin_demo_settings_view, name='admin_demo_settings'),
    # Email Settings
    path('admin/settings/email/', admin_settings_views.admin_email_settings_view, name='admin_email_settings'),
    # Security Settings
    path('admin/settings/security/', admin_settings_views.admin_security_settings_view, name='admin_security_settings'),
    # Maintenance Settings
    path('admin/settings/maintenance/', admin_settings_views.admin_maintenance_settings_view, name='admin_maintenance_settings'),
    # Backup Settings
    path('admin/settings/backup/', admin_settings_views.admin_backup_settings_view, name='admin_backup_settings'),
    # System Health
    path('admin/settings/health/', admin_settings_views.admin_system_health_view, name='admin_system_health'),
    # Cache Operations
    path('admin/settings/clear-cache/', admin_settings_views.admin_clear_cache, name='admin_clear_cache'),

    # =====================================
    # ADMIN NOTIFICATION MANAGEMENT
    # =====================================

    # Main Notifications Dashboard
    path('admin/notifications/', admin_notification_views.admin_notifications_view, name='admin_notifications'),

    # Notification Statistics and Settings
    path('admin/notifications/stats/', admin_notification_views.admin_notification_stats, name='admin_notification_stats'),
    path('admin/notifications/settings/', admin_notification_views.admin_notification_settings, name='admin_notification_settings'),

    # Notification Templates Management
    path('admin/notifications/templates/', admin_notification_views.admin_notification_templates_view, name='admin_notification_templates'),
    path('admin/notifications/templates/<int:template_id>/edit/', admin_notification_views.admin_edit_notification_template, name='admin_edit_notification_template'),

    # System Announcements
    path('admin/notifications/announcements/', admin_notification_views.admin_system_announcements_view, name='admin_system_announcements'),
    path('admin/notifications/announcements/create/', admin_notification_views.admin_create_announcement, name='admin_create_announcement'),
    path('admin/notifications/announcements/<int:announcement_id>/edit/', admin_notification_views.admin_edit_announcement, name='admin_edit_announcement'),
    path('admin/notifications/announcements/<int:announcement_id>/delete/', admin_notification_views.admin_delete_announcement, name='admin_delete_announcement'),

    # Bulk Operations
    path('admin/notifications/send-bulk/', admin_notification_views.admin_send_bulk_notification, name='admin_send_bulk_notification'),
    path('admin/notifications/bulk-actions/', admin_notification_views.admin_bulk_notification_actions, name='admin_bulk_notification_actions'),

    # Individual Notification Operations
    path('admin/notifications/<int:notification_id>/mark-read/', admin_notification_views.admin_mark_notification_read, name='admin_mark_notification_read'),
    path('admin/notifications/<int:notification_id>/delete/', admin_notification_views.admin_delete_notification, name='admin_delete_notification'),
        
    # =====================================
    # AJAX/API ENDPOINTS
    # =====================================
    
    # Customer Portal AJAX
    path('ajax/contact-sales/', views.ajax_contact_sales, name='ajax_contact_sales'),
    
    # Admin AJAX Endpoints
    path('ajax/system-health/', views.ajax_system_health, name='ajax_system_health'),
    path('ajax/validate-email/', views.validate_business_email_ajax, name='validate_business_email_ajax'),

    path('admin/customers/send-otp/', admin_customer_views.send_email_otp, name='admin_send_otp'),
    path('admin/customers/verify-otp/', admin_customer_views.verify_email_otp, name='admin_verify_otp'),

    path('admin/activity-analytics/', 
         user_activity_analytics_views.user_activity_analytics_page, 
         name='user_activity_analytics'),
    
    path('admin/ajax/activity-analytics/', 
         user_activity_analytics_views.ajax_activity_analytics, 
         name='ajax_activity_analytics'),
    
    path('admin/ajax/quick-stats/', 
         user_activity_analytics_views.ajax_quick_stats, 
         name='ajax_quick_stats'),

    path('admin/ajax/registration-data/', 
     user_activity_analytics_views.ajax_registration_data, 
     name='ajax_registration_data'),         

]