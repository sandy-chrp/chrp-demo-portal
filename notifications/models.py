# notifications/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

User = get_user_model()

class NotificationTemplate(models.Model):
    """Templates for different types of notifications"""
    
    NOTIFICATION_TYPES = [
        # Customer Notifications
        ('demo_confirmation', 'Demo Confirmation'),
        ('demo_reschedule', 'Demo Reschedule'),
        ('demo_cancellation', 'Demo Cancellation'),
        ('demo_rejection', 'Demo Rejection'),
        ('enquiry_received', 'Enquiry Received'),
        ('enquiry_response', 'Enquiry Response'),
        ('enquiry_status', 'Enquiry Status Change'),
        ('new_demo_available', 'New Demo Available'),
        ('account_approved', 'Account Approved'),
        ('account_blocked', 'Account Blocked'),
        ('account_unblocked', 'Account Unblocked'),
        ('password_reset', 'Password Reset'),
        ('profile_updated', 'Profile Updated'),
        ('system_announcement', 'System Announcement'),
        
        # Admin Notifications (NEW)
        ('new_customer', 'New Customer Registration'),
        ('demo_request', 'New Demo Request'),
        ('demo_request_cancelled', 'Demo Request Cancelled by Customer'),  # ✅ NEW
        ('enquiry', 'New Business Enquiry'),
        ('milestone', 'System Milestone'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Template Name")
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPES,
        unique=True,
        verbose_name="Notification Type"
    )
    
    # Email Template
    email_subject = models.CharField(max_length=200, verbose_name="Email Subject")
    email_body = models.TextField(
        verbose_name="Email Body",
        help_text="Use {{variable_name}} for dynamic content"
    )
    
    # In-App Template
    title_template = models.CharField(
        max_length=200,
        verbose_name="In-App Title",
        help_text="Use {{variable_name}} for dynamic content"
    )
    message_template = models.TextField(
        verbose_name="In-App Message",
        help_text="Use {{variable_name}} for dynamic content"
    )
    
    # Settings
    is_active = models.BooleanField(default=True, verbose_name="Active")
    send_email = models.BooleanField(default=True, verbose_name="Send Email")
    send_in_app = models.BooleanField(default=True, verbose_name="Send In-App")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_templates'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
    
    def __str__(self):
        return self.name

class Notification(models.Model):
    """User notifications"""
    
    NOTIFICATION_TYPES = NotificationTemplate.NOTIFICATION_TYPES
    
    # Recipient
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="User"
    )
    
    # Notification Content
    notification_type = models.CharField(
        max_length=30,
        choices=NOTIFICATION_TYPES,
        verbose_name="Type"
    )
    title = models.CharField(max_length=200, verbose_name="Title")
    message = models.TextField(verbose_name="Message")
    
    # Related Object (Generic Foreign Key)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Status
    is_read = models.BooleanField(default=False, verbose_name="Read")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Read At")
    
    # Email Status
    email_sent = models.BooleanField(default=False, verbose_name="Email Sent")
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True, verbose_name="Email Error")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.full_name}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

class SystemAnnouncement(models.Model):
    """System-wide announcements"""
    
    ANNOUNCEMENT_TYPES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('maintenance', 'Maintenance'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Title")
    message = models.TextField(verbose_name="Message")
    announcement_type = models.CharField(
        max_length=20,
        choices=ANNOUNCEMENT_TYPES,
        default='info',
        verbose_name="Type"
    )
    
    # Visibility
    is_active = models.BooleanField(default=True, verbose_name="Active")
    show_on_login = models.BooleanField(default=False, verbose_name="Show on Login")
    show_on_dashboard = models.BooleanField(default=True, verbose_name="Show on Dashboard")
    
    # Scheduling
    start_date = models.DateTimeField(verbose_name="Start Date")
    end_date = models.DateTimeField(verbose_name="End Date")
    
    # Creator
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_announcements',
        verbose_name="Created By"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_announcements'
        verbose_name = 'System Announcement'
        verbose_name_plural = 'System Announcements'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    @property
    def is_current(self):
        """Check if announcement is currently active"""
        from django.utils import timezone
        now = timezone.now()
        return (
            self.is_active and 
            self.start_date <= now <= self.end_date
        )