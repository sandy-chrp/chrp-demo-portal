# core/utils.py
"""
Utility functions for the core application
"""

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
import csv
import xlwt
from django.http import HttpResponse
from datetime import datetime


def is_admin(user):
    """
    Check if user is an admin (staff or superuser)
    Used with @user_passes_test decorator
    """
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def admin_required(view_func):
    """
    Decorator to require admin access for a view
    Alternative to using @login_required + @user_passes_test
    """
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('core:admin_login')
        
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'You do not have permission to access this page.')
            raise PermissionDenied
        
        return view_func(request, *args, **kwargs)
    
    return wrapped_view


def export_to_csv(modeladmin, request, queryset):
    """
    Generic CSV export function for admin actions
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{queryset.model.__name__.lower()}_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    # Get model fields
    fields = [field.name for field in queryset.model._meta.fields]
    writer.writerow(fields)
    
    # Write data
    for obj in queryset:
        row = []
        for field in fields:
            value = getattr(obj, field)
            if callable(value):
                value = value()
            row.append(str(value) if value is not None else '')
        writer.writerow(row)
    
    return response


def export_to_excel(modeladmin, request, queryset):
    """
    Generic Excel export function for admin actions
    """
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename="{queryset.model.__name__.lower()}_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xls"'
    
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet(queryset.model.__name__)
    
    # Sheet header, first row
    row_num = 0
    
    font_style = xlwt.XFStyle()
    font_style.font.bold = True
    
    # Get model fields
    fields = [field.name for field in queryset.model._meta.fields]
    
    for col_num in range(len(fields)):
        ws.write(row_num, col_num, fields[col_num], font_style)
    
    # Sheet body, remaining rows
    font_style = xlwt.XFStyle()
    
    for obj in queryset:
        row_num += 1
        for col_num in range(len(fields)):
            value = getattr(obj, fields[col_num])
            if callable(value):
                value = value()
            ws.write(row_num, col_num, str(value) if value is not None else '', font_style)
    
    wb.save(response)
    return response


def get_client_ip(request):
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def paginate_queryset(queryset, page_number, per_page=20):
    """
    Helper function to paginate querysets
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    paginator = Paginator(queryset, per_page)
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    return page_obj


def format_file_size(bytes):
    """
    Format file size in human readable format
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024.0:
            return f"{bytes:3.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} PB"


def send_admin_notification(subject, message, recipient_list=None):
    """
    Send notification email to admins
    """
    from django.core.mail import send_mail
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    if recipient_list is None:
        # Send to all admins
        recipient_list = User.objects.filter(
            is_staff=True, 
            is_active=True
        ).values_list('email', flat=True)
    
    if recipient_list:
        send_mail(
            subject=f"[Demo Portal Admin] {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(recipient_list),
            fail_silently=True
        )


def validate_business_email(email):
    """
    Check if email is a business email (not personal)
    Returns True if valid business email, False otherwise
    """
    blocked_domains = getattr(settings, 'BLOCKED_EMAIL_DOMAINS', [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'ymail.com', 'aol.com', 'icloud.com', 'live.com'
    ])
    
    if '@' not in email:
        return False
    
    domain = email.split('@')[1].lower()
    return domain not in blocked_domains


def get_dashboard_stats():
    """
    Get statistics for admin dashboard
    """
    from accounts.models import CustomUser
    from demos.models import Demo, DemoRequest, DemoView
    from enquiries.models import BusinessEnquiry
    from notifications.models import Notification
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    
    stats = {
        # User Statistics
        'total_users': CustomUser.objects.filter(is_active=True).count(),
        'pending_approvals': CustomUser.objects.filter(is_approved=False, is_active=True).count(),
        'verified_users': CustomUser.objects.filter(is_email_verified=True).count(),
        'new_users_30_days': CustomUser.objects.filter(created_at__date__gte=last_30_days).count(),
        
        # Demo Statistics
        'total_demos': Demo.objects.filter(is_active=True).count(),
        'featured_demos': Demo.objects.filter(is_featured=True, is_active=True).count(),
        'total_views': DemoView.objects.count(),
        'views_30_days': DemoView.objects.filter(viewed_at__date__gte=last_30_days).count(),
        
        # Demo Request Statistics
        'pending_demo_requests': DemoRequest.objects.filter(status='pending').count(),
        'confirmed_demo_requests': DemoRequest.objects.filter(status='confirmed').count(),
        'completed_demo_requests': DemoRequest.objects.filter(status='completed').count(),
        
        # Enquiry Statistics
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'in_progress_enquiries': BusinessEnquiry.objects.filter(status='in_progress').count(),
        'answered_enquiries': BusinessEnquiry.objects.filter(status='answered').count(),
        'overdue_enquiries': BusinessEnquiry.objects.filter(
            status='open',
            created_at__lt=timezone.now() - timedelta(hours=24)
        ).count(),
        
        # Notification Statistics
        'total_notifications': Notification.objects.count(),
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
        'notifications_today': Notification.objects.filter(created_at__date=today).count(),
    }
    
    return stats


def generate_unique_slug(model_class, title, slug_field='slug'):
    """
    Generate a unique slug for a model
    """
    from django.utils.text import slugify
    
    base_slug = slugify(title)
    if not base_slug:
        base_slug = 'item'
    
    unique_slug = base_slug
    counter = 1
    
    while model_class.objects.filter(**{slug_field: unique_slug}).exists():
        unique_slug = f"{base_slug}-{counter}"
        counter += 1
    
    return unique_slug


class AdminPermissionMixin:
    """
    Mixin to add admin permission check to class-based views
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('core:admin_login')
        
        if not is_admin(request.user):
            messages.error(request, 'You do not have permission to access this page.')
            raise PermissionDenied
        
        return super().dispatch(request, *args, **kwargs)