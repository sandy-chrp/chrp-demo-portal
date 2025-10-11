# notifications/api_views.py
"""Customer-facing notification APIs"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Notification
from .services import NotificationService
import logging

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def get_notifications_api(request):
    """Get user notifications"""
    try:
        limit = int(request.GET.get('limit', 10))
        unread_only = request.GET.get('unread_only', 'false') == 'true'
        
        notifications = Notification.objects.filter(user=request.user)
        
        if unread_only:
            notifications = notifications.filter(is_read=False)
        
        unread_count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        
        notifications = notifications[:limit]
        
        data = []
        for n in notifications:
            data.append({
                'id': n.id,
                'type': n.notification_type,
                'title': n.title,
                'message': n.message,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
                'time_ago': get_time_ago(n.created_at),
                'icon': get_icon(n.notification_type),
                'color': get_color(n.notification_type),
            })
        
        return JsonResponse({
            'success': True,
            'notifications': data,
            'unread_count': unread_count,
        })
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_as_read_api(request, notification_id):
    """Mark notification as read"""
    try:
        notification = get_object_or_404(
            Notification, id=notification_id, user=request.user
        )
        notification.mark_as_read()
        
        unread_count = NotificationService.get_unread_count(request.user)
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count,
        })
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_all_as_read_api(request):
    """Mark all notifications as read"""
    try:
        count = NotificationService.mark_all_as_read(request.user)
        
        return JsonResponse({
            'success': True,
            'count': count,
        })
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_unread_count_api(request):
    """Get unread count"""
    try:
        count = NotificationService.get_unread_count(request.user)
        return JsonResponse({'success': True, 'count': count})
    except Exception as e:
        logger.error(f"Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def get_time_ago(dt):
    """Convert to human readable time"""
    now = timezone.now()
    diff = (now - dt).total_seconds()
    
    if diff < 60:
        return 'Just now'
    elif diff < 3600:
        return f'{int(diff/60)} min ago'
    elif diff < 86400:
        return f'{int(diff/3600)} hour ago'
    elif diff < 604800:
        return f'{int(diff/86400)} day ago'
    else:
        return dt.strftime('%b %d')


def get_icon(notification_type):
    """Get icon for type"""
    icons = {
        'account_approved': 'fa-check-circle',
        'demo_confirmation': 'fa-calendar-check',
        'demo_reschedule': 'fa-calendar-alt',
        'demo_cancellation': 'fa-calendar-times',
        'enquiry_received': 'fa-envelope',
        'enquiry_response': 'fa-reply',
        'new_demo_available': 'fa-video',
    }
    return icons.get(notification_type, 'fa-bell')


def get_color(notification_type):
    """Get color for type"""
    colors = {
        'account_approved': 'success',
        'demo_confirmation': 'primary',
        'demo_reschedule': 'warning',
        'demo_cancellation': 'danger',
        'enquiry_received': 'info',
        'enquiry_response': 'success',
        'new_demo_available': 'primary',
    }
    return colors.get(notification_type, 'secondary')

@login_required
@require_http_methods(["DELETE"])
def delete_notification_api(request, notification_id):
    """Delete a notification"""
    try:
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            user=request.user
        )
        
        notification.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Notification deleted'
        })
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)