# notifications/admin_api_views.py

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from .models import Notification

@staff_member_required
@require_http_methods(["GET"])
def admin_unread_count(request):
    """Get unread notification count for admin"""
    count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({'count': count})


@staff_member_required
@require_http_methods(["GET"])
def admin_notification_list(request):
    """Get paginated list of admin notifications"""
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    filter_type = request.GET.get('filter', 'all')
    notification_type = request.GET.get('type', None)
    limit = request.GET.get('limit', None)
    
    # Base queryset
    notifications = Notification.objects.filter(user=request.user)
    
    # Apply filters
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_type == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Filter by notification type
    if notification_type:
        type_map = {
            'customer': 'new_customer',
            'demo': 'demo_request',
            'enquiry': 'enquiry',
            'milestone': 'milestone'
        }
        if notification_type in type_map:
            notifications = notifications.filter(
                notification_type=type_map[notification_type]
            )
    
    # Order by creation date (newest first)
    notifications = notifications.order_by('-created_at')
    
    # If limit is specified (for dropdown), just return that many
    if limit:
        notifications = notifications[:int(limit)]
        notification_list = []
        for notif in notifications:
            notification_list.append({
                'id': notif.id,
                'title': notif.title,
                'message': notif.message,
                'is_read': notif.is_read,
                'notification_type': notif.notification_type,
                'link': getattr(notif, 'link', None),
                'created_at': format_time_ago(notif.created_at)
            })
        
        return JsonResponse({
            'notifications': notification_list
        })
    
    # Pagination
    paginator = Paginator(notifications, per_page)
    page_obj = paginator.get_page(page)
    
    # Format notifications
    notification_list = []
    for notif in page_obj:
        notification_list.append({
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'is_read': notif.is_read,
            'notification_type': notif.notification_type,
            'link': getattr(notif, 'link', None), 
            'created_at': format_time_ago(notif.created_at)
        })
    
    return JsonResponse({
        'notifications': notification_list,
        'total': paginator.count,
        'page': page,
        'total_pages': paginator.num_pages,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous()
    })


def format_time_ago(dt):
    """Format datetime as time ago string"""
    now = timezone.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1):
        return 'Just now'
    elif diff < timedelta(hours=1):
        minutes = int(diff.total_seconds() / 60)
        return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    elif diff < timedelta(days=7):
        days = diff.days
        return f'{days} day{"s" if days != 1 else ""} ago'
    elif diff < timedelta(days=30):
        weeks = diff.days // 7
        return f'{weeks} week{"s" if weeks != 1 else ""} ago'
    elif diff < timedelta(days=365):
        months = diff.days // 30
        return f'{months} month{"s" if months != 1 else ""} ago'
    else:
        years = diff.days // 365
        return f'{years} year{"s" if years != 1 else ""} ago'


@staff_member_required
@require_http_methods(["POST"])
def admin_mark_as_read(request, notification_id):
    """Mark admin notification as read"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.is_read = True
        notification.save()
        
        return JsonResponse({
            'success': True,  # ✅ FIXED
            'message': 'Notification marked as read'
        })
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,  # ✅ FIXED
            'message': 'Notification not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,  # ✅ FIXED
            'message': str(e)
        }, status=500)


@staff_member_required
@require_http_methods(["POST"])
def admin_mark_all_as_read(request):
    """Mark all admin notifications as read"""
    try:
        count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        
        return JsonResponse({'success': True, 'count': count})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
@require_http_methods(["DELETE"])
def admin_delete_notification(request, notification_id):
    """Delete admin notification"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            user=request.user
        )
        notification.delete()
        
        return JsonResponse({'success': True})
        
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)