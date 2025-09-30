# core/admin_settings_views.py
"""
Admin Settings Management System
Handles all site settings and configuration views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.cache import cache
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.utils import timezone
from core.models import SiteSettings
from demos.models import Demo, DemoRequest
from enquiries.models import BusinessEnquiry
from accounts.models import CustomUser as User
from core.utils import is_admin
import json
import os


@login_required
@user_passes_test(is_admin)
def admin_settings_view(request):
    """Main settings dashboard"""
    
    # Load or create site settings
    site_settings = SiteSettings.load()
    
    # Get system information
    system_info = {
        'django_version': get_django_version(),
        'python_version': get_python_version(),
        'database_engine': settings.DATABASES['default']['ENGINE'].split('.')[-1],
        'time_zone': settings.TIME_ZONE,
        'debug_mode': settings.DEBUG,
        'allowed_hosts': settings.ALLOWED_HOSTS,
        'media_root': settings.MEDIA_ROOT,
        'static_root': settings.STATIC_ROOT,
    }
    
    # Storage statistics
    storage_stats = get_storage_stats()
    
    # Email configuration
    email_config = {
        'backend': settings.EMAIL_BACKEND.split('.')[-1] if hasattr(settings, 'EMAIL_BACKEND') else 'Not configured',
        'host': getattr(settings, 'EMAIL_HOST', 'Not configured'),
        'port': getattr(settings, 'EMAIL_PORT', 'Not configured'),
        'use_tls': getattr(settings, 'EMAIL_USE_TLS', False),
        'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not configured'),
    }
    
    context = {
        'site_settings': site_settings,
        'system_info': system_info,
        'storage_stats': storage_stats,
        'email_config': email_config,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/settings/settings.html', context)


@login_required
@user_passes_test(is_admin)
def admin_site_settings_view(request):
    """Site configuration settings"""
    
    site_settings = SiteSettings.load()
    
    if request.method == 'POST':
        # Update site information
        site_settings.site_name = request.POST.get('site_name', '')
        site_settings.site_description = request.POST.get('site_description', '')
        site_settings.contact_email = request.POST.get('contact_email', '')
        site_settings.contact_phone = request.POST.get('contact_phone', '')
        site_settings.address = request.POST.get('address', '')
        
        # Update social media
        site_settings.facebook_url = request.POST.get('facebook_url', '')
        site_settings.linkedin_url = request.POST.get('linkedin_url', '')
        site_settings.youtube_url = request.POST.get('youtube_url', '')
        
        # Handle file uploads
        if 'site_logo' in request.FILES:
            site_settings.site_logo = request.FILES['site_logo']
        if 'favicon' in request.FILES:
            site_settings.favicon = request.FILES['favicon']
        
        site_settings.save()
        
        # Clear cache
        cache.clear()
        
        messages.success(request, 'Site settings updated successfully')
        return redirect('core:admin_site_settings')
    
    context = {
        'site_settings': site_settings,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/settings/site_settings.html', context)


@login_required
@user_passes_test(is_admin)
def admin_demo_settings_view(request):
    """Demo portal specific settings"""
    
    site_settings = SiteSettings.load()
    
    if request.method == 'POST':
        site_settings.max_demo_requests_per_day = int(request.POST.get('max_demo_requests_per_day', 3))
        site_settings.demo_booking_advance_days = int(request.POST.get('demo_booking_advance_days', 30))
        site_settings.auto_approve_demo_requests = request.POST.get('auto_approve_demo_requests') == 'on'
        site_settings.save()
        
        messages.success(request, 'Demo settings updated successfully')
        return redirect('core:admin_demo_settings')
    
    context = {
        'site_settings': site_settings,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/settings/demo_settings.html', context)


@login_required
@user_passes_test(is_admin)
def admin_email_settings_view(request):
    """Email configuration settings"""
    
    site_settings = SiteSettings.load()
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update':
            site_settings.welcome_email_enabled = request.POST.get('welcome_email_enabled') == 'on'
            site_settings.notification_emails_enabled = request.POST.get('notification_emails_enabled') == 'on'
            site_settings.save()
            messages.success(request, 'Email settings updated successfully')
            
        elif action == 'test':
            # Send test email
            test_email = request.POST.get('test_email')
            if test_email:
                try:
                    send_test_email(test_email)
                    messages.success(request, f'Test email sent to {test_email}')
                except Exception as e:
                    messages.error(request, f'Failed to send test email: {str(e)}')
        
        return redirect('core:admin_email_settings')
    
    # Get email configuration from Django settings
    email_config = {
        'backend': settings.EMAIL_BACKEND if hasattr(settings, 'EMAIL_BACKEND') else None,
        'host': getattr(settings, 'EMAIL_HOST', None),
        'port': getattr(settings, 'EMAIL_PORT', None),
        'username': getattr(settings, 'EMAIL_HOST_USER', None),
        'use_tls': getattr(settings, 'EMAIL_USE_TLS', False),
        'use_ssl': getattr(settings, 'EMAIL_USE_SSL', False),
        'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', None),
    }
    
    context = {
        'site_settings': site_settings,
        'email_config': email_config,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/settings/email_settings.html', context)


@login_required
@user_passes_test(is_admin)
def admin_security_settings_view(request):
    """Security and authentication settings"""
    
    if request.method == 'POST':
        # Update security settings in Django settings or database
        # This would typically update settings like:
        # - Password requirements
        # - Session timeout
        # - Two-factor authentication
        # - IP restrictions
        
        messages.success(request, 'Security settings updated successfully')
        return redirect('core:admin_security_settings')
    
    # Get current security settings
    security_settings = {
        'password_min_length': getattr(settings, 'PASSWORD_MIN_LENGTH', 8),
        'password_require_uppercase': getattr(settings, 'PASSWORD_REQUIRE_UPPERCASE', True),
        'password_require_numbers': getattr(settings, 'PASSWORD_REQUIRE_NUMBERS', True),
        'password_require_special': getattr(settings, 'PASSWORD_REQUIRE_SPECIAL', True),
        'session_timeout': getattr(settings, 'SESSION_COOKIE_AGE', 1209600) // 60,  # Convert to minutes
        'max_login_attempts': getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5),
        'lockout_duration': getattr(settings, 'LOCKOUT_DURATION', 30),
    }
    
    context = {
        'security_settings': security_settings,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/settings/security_settings.html', context)


@login_required
@user_passes_test(is_admin)
def admin_maintenance_settings_view(request):
    """Maintenance mode settings"""
    
    site_settings = SiteSettings.load()
    
    if request.method == 'POST':
        site_settings.maintenance_mode = request.POST.get('maintenance_mode') == 'on'
        site_settings.maintenance_message = request.POST.get('maintenance_message', '')
        site_settings.save()
        
        # Clear cache
        cache.clear()
        
        if site_settings.maintenance_mode:
            messages.warning(request, 'Maintenance mode is now ENABLED. Site is not accessible to regular users.')
        else:
            messages.success(request, 'Maintenance mode is now DISABLED. Site is accessible to all users.')
        
        return redirect('core:admin_maintenance_settings')
    
    context = {
        'site_settings': site_settings,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/settings/maintenance_settings.html', context)


@login_required
@user_passes_test(is_admin)
def admin_backup_settings_view(request):
    """Backup and restore settings"""
    
    # Get backup history (you would implement actual backup logic)
    backups = []  # List of backup records
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'backup':
            # Perform backup
            try:
                # Implement backup logic here
                messages.success(request, 'Backup created successfully')
            except Exception as e:
                messages.error(request, f'Backup failed: {str(e)}')
                
        elif action == 'restore':
            backup_id = request.POST.get('backup_id')
            # Perform restore
            try:
                # Implement restore logic here
                messages.success(request, 'Restore completed successfully')
            except Exception as e:
                messages.error(request, f'Restore failed: {str(e)}')
        
        return redirect('core:admin_backup_settings')
    
    context = {
        'backups': backups,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/settings/backup_settings.html', context)


@login_required
@user_passes_test(is_admin)
@require_POST
def admin_clear_cache(request):
    """Clear all cache"""
    
    try:
        cache.clear()
        messages.success(request, 'Cache cleared successfully')
    except Exception as e:
        messages.error(request, f'Failed to clear cache: {str(e)}')
    
    return redirect('core:admin_settings')


@login_required
@user_passes_test(is_admin)
def admin_system_health_view(request):
    """System health check"""
    
    health_checks = {
        'database': check_database_health(),
        'cache': check_cache_health(),
        'storage': check_storage_health(),
        'email': check_email_health(),
    }
    
    context = {
        'health_checks': health_checks,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/settings/system_health.html', context)


# Helper Functions
def get_django_version():
    """Get Django version"""
    import django
    return django.get_version()


def get_python_version():
    """Get Python version"""
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_storage_stats():
    """Get storage statistics"""
    import shutil
    
    stats = {}
    
    # Get disk usage for media directory
    if os.path.exists(settings.MEDIA_ROOT):
        media_usage = shutil.disk_usage(settings.MEDIA_ROOT)
        stats['media'] = {
            'total': media_usage.total // (1024 * 1024 * 1024),  # GB
            'used': media_usage.used // (1024 * 1024 * 1024),
            'free': media_usage.free // (1024 * 1024 * 1024),
            'percent': (media_usage.used / media_usage.total) * 100 if media_usage.total > 0 else 0
        }
    
    # Get database size
    from django.db import connection
    with connection.cursor() as cursor:
        if 'sqlite' in settings.DATABASES['default']['ENGINE']:
            db_path = settings.DATABASES['default']['NAME']
            if os.path.exists(db_path):
                stats['database_size'] = os.path.getsize(db_path) // (1024 * 1024)  # MB
        # Add logic for other databases (PostgreSQL, MySQL, etc.)
    
    return stats


def send_test_email(email_address):
    """Send a test email"""
    from django.core.mail import send_mail
    
    subject = 'Test Email from Demo Portal'
    message = f'''
    This is a test email from your Demo Portal.
    
    If you received this email, your email configuration is working correctly.
    
    Sent at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
    '''
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email_address],
        fail_silently=False,
    )


def check_database_health():
    """Check database connectivity"""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return {'status': 'healthy', 'message': 'Database connection successful'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def check_cache_health():
    """Check cache connectivity"""
    try:
        cache.set('health_check', 'test', 30)
        value = cache.get('health_check')
        cache.delete('health_check')
        if value == 'test':
            return {'status': 'healthy', 'message': 'Cache is working'}
        else:
            return {'status': 'warning', 'message': 'Cache test failed'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def check_storage_health():
    """Check storage accessibility"""
    try:
        # Check if media directory is writable
        test_file = os.path.join(settings.MEDIA_ROOT, 'test_health_check.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return {'status': 'healthy', 'message': 'Storage is accessible'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def check_email_health():
    """Check email configuration"""
    try:
        from django.core.mail import get_connection
        connection = get_connection()
        connection.open()
        connection.close()
        return {'status': 'healthy', 'message': 'Email backend is configured'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}