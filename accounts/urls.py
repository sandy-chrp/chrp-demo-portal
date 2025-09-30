# accounts/urls.py - Complete URL configuration
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication with OTP
    path('signup/', views.signup_view, name='signup'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('signin/', views.signin_view, name='signin'),
    path('signout/', views.signout_view, name='signout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password_view, name='reset_password'),
    
    # Email Verification (old method - optional)
    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),
    path('resend-verification/', views.resend_verification_view, name='resend_verification'),
    
    # Profile Management
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    # Account Status
    path('pending-approval/', views.pending_approval_view, name='pending_approval'),
    path('account-blocked/', views.account_blocked_view, name='account_blocked'),
    
    # AJAX Endpoints
    path('ajax/get-subcategories/', views.get_subcategories, name='get_subcategories'),
    path('ajax/get-country-from-ip/', views.get_country_from_ip, name='get_country_from_ip'),
    path('ajax/check-email-exists/', views.check_email_exists, name='check_email_exists'),
    path('ajax/contact-sales/', views.contact_sales_view, name='contact_sales_ajax'),
]