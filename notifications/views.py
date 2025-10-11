# notifications/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import Notification
from .services import NotificationService


@login_required
def notification_list_view(request):
    """
    Notification center page - shows all notifications
    """
    # Get filter type
    filter_type = request.GET.get('filter', 'all')
    
    # Build query
    notifications = Notification.objects.filter(user=request.user).select_related('content_type')
    
    # Apply filter
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    
    # Add notification metadata
    notifications_list = []
    for notif in notifications:
        notif.icon = get_notification_icon(notif.notification_type)
        notif.color = get_notification_color(notif.notification_type)
        notifications_list.append(notif)
    
    # Paginate
    paginator = Paginator(notifications_list, 20)
    page_number = request.GET.get('page', 1)
    notifications_page = paginator.get_page(page_number)
    
    # Get counts
    unread_count = NotificationService.get_unread_count(request.user)
    total_count = Notification.objects.filter(user=request.user).count()
    
    context = {
        'notifications': notifications_page,
        'filter_type': filter_type,
        'unread_count': unread_count,
        'total_count': total_count,
    }
    
    return render(request, 'notifications/list.html', context)


def get_notification_icon(notification_type):
    """Get icon for notification type"""
    icons = {
        'account_approved': 'fa-check-circle',
        'demo_confirmation': 'fa-calendar-check',
        'demo_reschedule': 'fa-calendar-alt',
        'demo_cancellation': 'fa-calendar-times',
        'enquiry_received': 'fa-envelope',
        'enquiry_response': 'fa-reply',
        'new_demo_available': 'fa-video',
        'system_announcement': 'fa-bullhorn',
    }
    return icons.get(notification_type, 'fa-bell')


def get_notification_color(notification_type):
    """Get color for notification type"""
    colors = {
        'account_approved': 'success',
        'demo_confirmation': 'primary',
        'demo_reschedule': 'warning',
        'demo_cancellation': 'danger',
        'enquiry_received': 'info',
        'enquiry_response': 'success',
        'new_demo_available': 'primary',
        'system_announcement': 'secondary',
    }
    return colors.get(notification_type, 'secondary')