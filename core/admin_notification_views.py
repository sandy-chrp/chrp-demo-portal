# core/admin_notification_views.py
"""
Admin Notification Management System
Handles all notification-related views for the admin panel
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import timedelta
from notifications.models import Notification, NotificationTemplate, SystemAnnouncement
from demos.models import DemoRequest, Demo
from enquiries.models import BusinessEnquiry
from accounts.models import CustomUser as User
from core.utils import is_admin
import json


@login_required
@user_passes_test(is_admin)
def admin_notifications_view(request):
    """Main notifications dashboard"""
    
    # Get filter parameters
    filter_type = request.GET.get('type', 'all')
    filter_status = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')
    
    # Base queryset
    notifications = Notification.objects.select_related('user').order_by('-created_at')
    
    # Apply filters
    if filter_type != 'all':
        notifications = notifications.filter(notification_type=filter_type)
    
    if filter_status == 'read':
        notifications = notifications.filter(is_read=True)
    elif filter_status == 'unread':
        notifications = notifications.filter(is_read=False)
    
    if search_query:
        notifications = notifications.filter(
            Q(title__icontains=search_query) |
            Q(message__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page')
    notifications_page = paginator.get_page(page)
    
    # Statistics
    stats = {
        'total_notifications': Notification.objects.count(),
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
        'today_notifications': Notification.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
        'email_sent': Notification.objects.filter(email_sent=True).count(),
        'email_failed': Notification.objects.filter(
            email_sent=False,
            email_error__isnull=False
        ).exclude(email_error='').count(),
    }
    
    # Notification type distribution
    type_distribution = Notification.objects.values('notification_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Recent system announcements
    announcements = SystemAnnouncement.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).order_by('-created_at')[:5]
    
    # Pending items that need notifications
    pending_items = {
        'pending_approvals': User.objects.filter(
            is_approved=False, 
            is_active=True
        ).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'pending_demo_requests': DemoRequest.objects.filter(status='pending').count(),
        'overdue_enquiries': BusinessEnquiry.objects.filter(
            status='open',
            created_at__lt=timezone.now() - timedelta(hours=24)
        ).count(),
    }
    
    context = {
        'notifications': notifications_page,
        'stats': stats,
        'type_distribution': type_distribution,
        'announcements': announcements,
        'pending_items': pending_items,
        'filter_type': filter_type,
        'filter_status': filter_status,
        'search_query': search_query,
        'notification_types': NotificationTemplate.NOTIFICATION_TYPES,
        
        # For base template
        'pending_approvals': pending_items['pending_approvals'],
        'open_enquiries': pending_items['open_enquiries'],
        'demo_requests_pending': pending_items['pending_demo_requests'],
    }
    
    return render(request, 'admin/notifications/notifications.html', context)


@login_required
@user_passes_test(is_admin)
def admin_notification_templates_view(request):
    """Manage notification templates"""
    
    templates = NotificationTemplate.objects.all().order_by('notification_type')
    
    context = {
        'templates': templates,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/notifications/templates.html', context)


@login_required
@user_passes_test(is_admin)
def admin_edit_notification_template(request, template_id):
    """Edit notification template"""
    
    template = get_object_or_404(NotificationTemplate, id=template_id)
    
    if request.method == 'POST':
        template.name = request.POST.get('name')
        template.email_subject = request.POST.get('email_subject')
        template.email_body = request.POST.get('email_body')
        template.title_template = request.POST.get('title_template')
        template.message_template = request.POST.get('message_template')
        template.is_active = request.POST.get('is_active') == 'on'
        template.send_email = request.POST.get('send_email') == 'on'
        template.send_in_app = request.POST.get('send_in_app') == 'on'
        template.save()
        
        messages.success(request, f'Template "{template.name}" updated successfully')
        return redirect('core:admin_notification_templates')
    
    # Available variables for templates
    template_variables = {
        'demo_confirmation': ['user_name', 'demo_title', 'requested_date', 'time_slot'],
        'demo_reschedule': ['user_name', 'demo_title', 'old_date', 'new_date', 'time_slot'],
        'demo_cancellation': ['user_name', 'demo_title', 'cancelled_date', 'reason'],
        'enquiry_received': ['enquiry_id', 'user_name', 'subject', 'organization'],
        'enquiry_response': ['enquiry_id', 'user_name', 'response_summary'],
        'new_demo_available': ['demo_title', 'category', 'duration'],
        'account_approved': ['user_name', 'approval_date'],
        'system_announcement': ['title', 'message', 'priority'],
    }
    
    context = {
        'template': template,
        'template_variables': template_variables.get(template.notification_type, []),
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/notifications/edit_template.html', context)


@login_required
@user_passes_test(is_admin)
def admin_system_announcements_view(request):
    """Manage system announcements"""
    
    # Get filter parameters
    filter_status = request.GET.get('status', 'all')
    
    announcements = SystemAnnouncement.objects.select_related('created_by').order_by('-created_at')
    
    if filter_status == 'active':
        now = timezone.now()
        announcements = announcements.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        )
    elif filter_status == 'scheduled':
        announcements = announcements.filter(
            start_date__gt=timezone.now()
        )
    elif filter_status == 'expired':
        announcements = announcements.filter(
            end_date__lt=timezone.now()
        )
    
    # Pagination
    paginator = Paginator(announcements, 10)
    page = request.GET.get('page')
    announcements_page = paginator.get_page(page)
    
    context = {
        'announcements': announcements_page,
        'filter_status': filter_status,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/notifications/announcements.html', context)


@login_required
@user_passes_test(is_admin)
def admin_create_announcement(request):
    """Create new system announcement"""
    
    if request.method == 'POST':
        announcement = SystemAnnouncement(
            title=request.POST.get('title'),
            message=request.POST.get('message'),
            announcement_type=request.POST.get('announcement_type'),
            is_active=request.POST.get('is_active') == 'on',
            show_on_login=request.POST.get('show_on_login') == 'on',
            show_on_dashboard=request.POST.get('show_on_dashboard') == 'on',
            start_date=request.POST.get('start_date'),
            end_date=request.POST.get('end_date'),
            created_by=request.user
        )
        announcement.save()
        
        # Create notifications for all active users if requested
        if request.POST.get('notify_users') == 'on':
            active_users = User.objects.filter(is_active=True)
            for user in active_users:
                Notification.objects.create(
                    user=user,
                    notification_type='system_announcement',
                    title=announcement.title,
                    message=announcement.message[:500],  # Truncate if too long
                    content_object=announcement
                )
        
        messages.success(request, f'Announcement "{announcement.title}" created successfully')
        return redirect('core:admin_system_announcements')
    
    context = {
        'announcement_types': SystemAnnouncement.ANNOUNCEMENT_TYPES,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/notifications/create_announcement.html', context)


@login_required
@user_passes_test(is_admin)
def admin_edit_announcement(request, announcement_id):
    """Edit system announcement"""
    
    announcement = get_object_or_404(SystemAnnouncement, id=announcement_id)
    
    if request.method == 'POST':
        announcement.title = request.POST.get('title')
        announcement.message = request.POST.get('message')
        announcement.announcement_type = request.POST.get('announcement_type')
        announcement.is_active = request.POST.get('is_active') == 'on'
        announcement.show_on_login = request.POST.get('show_on_login') == 'on'
        announcement.show_on_dashboard = request.POST.get('show_on_dashboard') == 'on'
        announcement.start_date = request.POST.get('start_date')
        announcement.end_date = request.POST.get('end_date')
        announcement.save()
        
        messages.success(request, f'Announcement "{announcement.title}" updated successfully')
        return redirect('core:admin_system_announcements')
    
    context = {
        'announcement': announcement,
        'announcement_types': SystemAnnouncement.ANNOUNCEMENT_TYPES,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/notifications/edit_announcement.html', context)


@login_required
@user_passes_test(is_admin)
@require_POST
def admin_delete_announcement(request, announcement_id):
    """Delete system announcement"""
    
    announcement = get_object_or_404(SystemAnnouncement, id=announcement_id)
    announcement.delete()
    
    messages.success(request, 'Announcement deleted successfully')
    return redirect('core:admin_system_announcements')


@login_required
@user_passes_test(is_admin)
def admin_send_bulk_notification(request):
    """Send bulk notifications to users"""
    
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        notification_type = request.POST.get('notification_type', 'system_announcement')
        user_filter = request.POST.get('user_filter')
        
        # Select users based on filter
        users = User.objects.filter(is_active=True)
        
        if user_filter == 'approved':
            users = users.filter(is_approved=True)
        elif user_filter == 'verified':
            users = users.filter(is_email_verified=True)
        elif user_filter == 'recent':
            cutoff_date = timezone.now() - timedelta(days=30)
            users = users.filter(created_at__gte=cutoff_date)
        elif user_filter == 'specific':
            user_ids = request.POST.getlist('specific_users')
            users = users.filter(id__in=user_ids)
        
        # Create notifications
        notifications_created = 0
        for user in users:
            Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message
            )
            notifications_created += 1
        
        messages.success(request, f'Successfully sent {notifications_created} notifications')
        return redirect('core:admin_notifications')
    
    # Get users for specific selection
    all_users = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
    
    context = {
        'all_users': all_users,
        'notification_types': NotificationTemplate.NOTIFICATION_TYPES,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/notifications/send_bulk.html', context)


@login_required
@user_passes_test(is_admin)
@require_POST
def admin_mark_notification_read(request, notification_id):
    """Mark notification as read"""
    
    notification = get_object_or_404(Notification, id=notification_id)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('core:admin_notifications')


@login_required
@user_passes_test(is_admin)
@require_POST
def admin_delete_notification(request, notification_id):
    """Delete a notification"""
    
    notification = get_object_or_404(Notification, id=notification_id)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    messages.success(request, 'Notification deleted successfully')
    return redirect('core:admin_notifications')


@login_required
@user_passes_test(is_admin)
@require_POST
def admin_bulk_notification_actions(request):
    """Handle bulk actions on notifications"""
    
    action = request.POST.get('action')
    notification_ids = request.POST.getlist('notification_ids')
    
    if not notification_ids:
        messages.error(request, 'No notifications selected')
        return redirect('core:admin_notifications')
    
    notifications = Notification.objects.filter(id__in=notification_ids)
    
    if action == 'mark_read':
        notifications.update(is_read=True, read_at=timezone.now())
        messages.success(request, f'{len(notification_ids)} notifications marked as read')
    
    elif action == 'mark_unread':
        notifications.update(is_read=False, read_at=None)
        messages.success(request, f'{len(notification_ids)} notifications marked as unread')
    
    elif action == 'delete':
        count = notifications.count()
        notifications.delete()
        messages.success(request, f'{count} notifications deleted')
    
    return redirect('core:admin_notifications')


@login_required
@user_passes_test(is_admin)
def admin_notification_stats(request):
    """View detailed notification statistics"""
    
    # Date range filter
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    
    notifications = Notification.objects.all()
    
    if date_from:
        notifications = notifications.filter(created_at__gte=date_from)
    if date_to:
        notifications = notifications.filter(created_at__lte=date_to)
    
    # Calculate statistics
    stats = {
        'total': notifications.count(),
        'read_rate': notifications.filter(is_read=True).count() / notifications.count() * 100 if notifications.count() > 0 else 0,
        'email_success_rate': notifications.filter(email_sent=True).count() / notifications.count() * 100 if notifications.count() > 0 else 0,
        'by_type': notifications.values('notification_type').annotate(count=Count('id')),
        'by_day': notifications.extra(select={'day': 'date(created_at)'}).values('day').annotate(count=Count('id')).order_by('day'),
        'top_users': notifications.values('user__email', 'user__first_name', 'user__last_name').annotate(count=Count('id')).order_by('-count')[:10],
    }
    
    context = {
        'stats': stats,
        'date_from': date_from,
        'date_to': date_to,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/notifications/stats.html', context)


@login_required
@user_passes_test(is_admin)
def admin_notification_settings(request):
    """Global notification settings"""
    
    if request.method == 'POST':
        # Handle settings update
        settings_data = {
            'email_enabled': request.POST.get('email_enabled') == 'on',
            'in_app_enabled': request.POST.get('in_app_enabled') == 'on',
            'auto_delete_days': int(request.POST.get('auto_delete_days', 90)),
            'batch_size': int(request.POST.get('batch_size', 100)),
        }
        
        # Save settings (you might want to use a Settings model or cache)
        messages.success(request, 'Notification settings updated successfully')
        return redirect('core:admin_notification_settings')
    
    # Load current settings
    settings_data = {
        'email_enabled': True,
        'in_app_enabled': True,
        'auto_delete_days': 90,
        'batch_size': 100,
    }
    
    context = {
        'settings': settings_data,
        'pending_approvals': User.objects.filter(is_approved=False, is_active=True).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(status='open').count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
    }
    
    return render(request, 'admin/notifications/settings.html', context)


# ===============================================
# TEMPLATES
# ===============================================

"""
Create the following template files in templates/admin/notifications/

1. templates/admin/notifications/notifications.html
2. templates/admin/notifications/templates.html
3. templates/admin/notifications/edit_template.html
4. templates/admin/notifications/announcements.html
5. templates/admin/notifications/create_announcement.html
6. templates/admin/notifications/edit_announcement.html
7. templates/admin/notifications/send_bulk.html
8. templates/admin/notifications/stats.html
9. templates/admin/notifications/settings.html
"""