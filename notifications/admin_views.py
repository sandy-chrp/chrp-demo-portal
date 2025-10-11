# notifications/admin_views.py

from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from accounts.models import CustomUser
from .services import NotificationService

@staff_member_required
def admin_notification_center(request):
    """Admin notification center page"""
    return render(request, 'notifications/admin_notifications.html')


@staff_member_required
def admin_notification_preferences(request):
    """Admin notification preferences page"""
    if request.method == 'POST':
        messages.success(request, 'Notification preferences updated successfully!')
        return redirect('admin_notification_preferences')
    
    return render(request, 'notifications/admin_preferences.html')


@staff_member_required
def admin_send_bulk_notification(request):
    """Send bulk notifications to customers"""
    if request.method == 'POST':
        title = request.POST.get('title')
        message = request.POST.get('message')
        recipient_type = request.POST.get('recipient_type', 'all')
        send_email = request.POST.get('send_email') == 'on'
        
        # Validate inputs
        if not title or not message:
            messages.error(request, 'Title and message are required!')
            return redirect('admin_send_bulk')
        
        # Get recipients based on type
        if recipient_type == 'active':
            recipients = CustomUser.objects.filter(is_active=True, is_staff=False)
        elif recipient_type == 'inactive':
            recipients = CustomUser.objects.filter(is_active=False, is_staff=False)
        else:  # all
            recipients = CustomUser.objects.filter(is_staff=False)
        
        # Send notifications
        count = 0
        for user in recipients:
            try:
                NotificationService.send_custom_notification(
                    user=user,
                    title=title,
                    message=message,
                    notification_type='system_announcement',
                    send_email=send_email
                )
                count += 1
            except Exception as e:
                print(f"Error sending notification to {user.email}: {e}")
        
        messages.success(request, f'Bulk notification sent to {count} users!')
        return redirect('admin_send_bulk')
    
    # Get user statistics
    total_users = CustomUser.objects.filter(is_staff=False).count()
    active_users = CustomUser.objects.filter(is_active=True, is_staff=False).count()
    inactive_users = CustomUser.objects.filter(is_active=False, is_staff=False).count()
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
    }
    
    return render(request, 'notifications/admin_bulk_send.html', context)