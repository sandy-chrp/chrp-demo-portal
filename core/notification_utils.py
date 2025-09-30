# core/notification_utils.py
"""
Utility functions for creating and managing notifications
Based on the requirements document and database models
"""

from django.utils import timezone
from django.template import Template, Context
from django.core.mail import send_mail
from django.conf import settings
from notifications.models import Notification, NotificationTemplate
from demos.models import DemoRequest, Demo
from enquiries.models import BusinessEnquiry
from accounts.models import CustomUser as User
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service class to handle all notification creation and sending
    """
    
    @staticmethod
    def create_notification(user, notification_type, context_data=None, send_email=True):
        """
        Create a notification for a user based on template
        
        Args:
            user: User object
            notification_type: Type of notification
            context_data: Dictionary with template variables
            send_email: Whether to send email notification
        """
        try:
            # Get template
            template = NotificationTemplate.objects.filter(
                notification_type=notification_type,
                is_active=True
            ).first()
            
            if not template:
                logger.warning(f"No active template found for {notification_type}")
                return None
            
            # Prepare context
            context = Context(context_data or {})
            
            # Render templates
            title = Template(template.title_template).render(context)
            message = Template(template.message_template).render(context)
            
            # Create notification
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message
            )
            
            # Send email if enabled
            if send_email and template.send_email:
                NotificationService.send_email_notification(
                    user, template, context_data, notification
                )
            
            return notification
            
        except Exception as e:
            logger.error(f"Error creating notification: {str(e)}")
            return None
    
    @staticmethod
    def send_email_notification(user, template, context_data, notification):
        """
        Send email notification to user
        """
        try:
            context = Context(context_data or {})
            subject = Template(template.email_subject).render(context)
            body = Template(template.email_body).render(context)
            
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=body,
                fail_silently=False
            )
            
            notification.email_sent = True
            notification.email_sent_at = timezone.now()
            notification.save(update_fields=['email_sent', 'email_sent_at'])
            
        except Exception as e:
            notification.email_error = str(e)
            notification.save(update_fields=['email_error'])
            logger.error(f"Error sending email notification: {str(e)}")
    
    # =========================================
    # Specific notification creators based on requirements document
    # =========================================
    
    @staticmethod
    def notify_demo_confirmation(demo_request):
        """
        Send notification when demo request is confirmed
        As per requirement: Demo confirmations or reschedules
        """
        context_data = {
            'user_name': demo_request.user.full_name,
            'demo_title': demo_request.demo.title,
            'requested_date': demo_request.effective_date.strftime('%B %d, %Y'),
            'time_slot': str(demo_request.effective_time_slot),
        }
        
        return NotificationService.create_notification(
            user=demo_request.user,
            notification_type='demo_confirmation',
            context_data=context_data
        )
    
    @staticmethod
    def notify_demo_reschedule(demo_request, old_date, old_slot):
        """
        Send notification when demo is rescheduled
        As per requirement: Demo confirmations or reschedules
        """
        context_data = {
            'user_name': demo_request.user.full_name,
            'demo_title': demo_request.demo.title,
            'old_date': old_date.strftime('%B %d, %Y'),
            'new_date': demo_request.confirmed_date.strftime('%B %d, %Y'),
            'time_slot': str(demo_request.confirmed_time_slot),
        }
        
        return NotificationService.create_notification(
            user=demo_request.user,
            notification_type='demo_reschedule',
            context_data=context_data
        )
    
    @staticmethod
    def notify_demo_cancellation(demo_request, reason=''):
        """
        Send notification when demo is cancelled
        """
        context_data = {
            'user_name': demo_request.user.full_name,
            'demo_title': demo_request.demo.title,
            'cancelled_date': demo_request.requested_date.strftime('%B %d, %Y'),
            'reason': reason or 'No reason provided',
        }
        
        return NotificationService.create_notification(
            user=demo_request.user,
            notification_type='demo_cancellation',
            context_data=context_data
        )
    
    @staticmethod
    def notify_enquiry_received(enquiry):
        """
        Send notification when enquiry is received
        As per requirement: Enquiry updates (status changes)
        """
        context_data = {
            'enquiry_id': enquiry.enquiry_id,
            'user_name': enquiry.full_name,
            'subject': enquiry.subject or 'Business Enquiry',
            'organization': enquiry.organization,
        }
        
        return NotificationService.create_notification(
            user=enquiry.user,
            notification_type='enquiry_received',
            context_data=context_data
        )
    
    @staticmethod
    def notify_enquiry_response(enquiry, response_summary=''):
        """
        Send notification when enquiry gets a response
        As per requirement: Enquiry updates (status changes)
        """
        context_data = {
            'enquiry_id': enquiry.enquiry_id,
            'user_name': enquiry.full_name,
            'response_summary': response_summary[:200] if response_summary else 'Your enquiry has been answered.',
        }
        
        return NotificationService.create_notification(
            user=enquiry.user,
            notification_type='enquiry_response',
            context_data=context_data
        )
    
    @staticmethod
    def notify_new_demo_available(demo, target_users=None):
        """
        Send notification for new demo availability
        As per requirement: New demo availability announcements
        """
        context_data = {
            'demo_title': demo.title,
            'category': demo.category.name if demo.category else 'General',
            'duration': demo.formatted_duration,
        }
        
        # If no specific users, notify all approved users
        if target_users is None:
            # Check if demo is for specific customers
            if demo.target_customers.exists():
                target_users = demo.target_customers.all()
            else:
                target_users = User.objects.filter(
                    is_active=True, 
                    is_approved=True
                )
        
        notifications = []
        for user in target_users:
            notification = NotificationService.create_notification(
                user=user,
                notification_type='new_demo_available',
                context_data=context_data
            )
            if notification:
                notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def notify_account_approved(user):
        """
        Send notification when account is approved
        As per requirement: Customer signs up → Verified → Gains access
        """
        context_data = {
            'user_name': user.full_name,
            'approval_date': timezone.now().strftime('%B %d, %Y'),
        }
        
        return NotificationService.create_notification(
            user=user,
            notification_type='account_approved',
            context_data=context_data
        )
    
    @staticmethod
    def bulk_create_notifications(users, title, message, notification_type='system_announcement'):
        """
        Create bulk notifications for multiple users
        As per requirement: Admin messages/alerts
        """
        notifications = []
        for user in users:
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message
            )
            notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def get_user_unread_count(user):
        """
        Get unread notification count for user
        For displaying in bell icon as per requirement
        """
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).count()
    
    @staticmethod
    def mark_all_as_read(user):
        """
        Mark all notifications as read for a user
        """
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
    
    @staticmethod
    def cleanup_old_notifications(days=90):
        """
        Clean up old notifications
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return Notification.objects.filter(
            created_at__lt=cutoff_date,
            is_read=True
        ).delete()


# =========================================
# Signal handlers to automatically create notifications
# =========================================
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(post_save, sender=DemoRequest)
def handle_demo_request_notification(sender, instance, created, **kwargs):
    """
    Automatically create notifications for demo request status changes
    """
    if not created:
        # Check if status changed
        if hasattr(instance, '_old_status'):
            old_status = instance._old_status
            new_status = instance.status
            
            if old_status != new_status:
                if new_status == 'confirmed':
                    NotificationService.notify_demo_confirmation(instance)
                elif new_status == 'cancelled':
                    NotificationService.notify_demo_cancellation(instance)
                elif new_status == 'rescheduled':
                    # Need to pass old date/slot if available
                    NotificationService.notify_demo_reschedule(
                        instance, 
                        instance.requested_date,
                        instance.requested_time_slot
                    )


@receiver(pre_save, sender=DemoRequest)
def store_old_status(sender, instance, **kwargs):
    """
    Store old status before save for comparison
    """
    if instance.pk:
        try:
            old_instance = DemoRequest.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except DemoRequest.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender=BusinessEnquiry)
def handle_enquiry_notification(sender, instance, created, **kwargs):
    """
    Automatically create notifications for enquiry status changes
    """
    if created:
        # Send notification for new enquiry
        NotificationService.notify_enquiry_received(instance)
    else:
        # Check if status changed to answered
        if hasattr(instance, '_old_status'):
            old_status = instance._old_status
            new_status = instance.status
            
            if old_status != new_status and new_status == 'answered':
                NotificationService.notify_enquiry_response(instance)


@receiver(pre_save, sender=BusinessEnquiry)
def store_old_enquiry_status(sender, instance, **kwargs):
    """
    Store old status before save for comparison
    """
    if instance.pk:
        try:
            old_instance = BusinessEnquiry.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except BusinessEnquiry.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender=User)
def handle_user_approval_notification(sender, instance, created, **kwargs):
    """
    Send notification when user account is approved
    As per requirement: Customer signs up → Verified → Gains access
    """
    if not created and instance.is_approved:
        # Check if approval status changed
        if hasattr(instance, '_old_is_approved'):
            if not instance._old_is_approved and instance.is_approved:
                NotificationService.notify_account_approved(instance)


@receiver(pre_save, sender=User)
def store_old_approval_status(sender, instance, **kwargs):
    """
    Store old approval status before save
    """
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            instance._old_is_approved = old_instance.is_approved
        except User.DoesNotExist:
            instance._old_is_approved = False


@receiver(post_save, sender=Demo)
def handle_new_demo_notification(sender, instance, created, **kwargs):
    """
    Send notification for new demo availability
    As per requirement: New demo availability announcements
    """
    if created and instance.is_active:
        NotificationService.notify_new_demo_available(instance)


# =========================================
# Template initialization data
# =========================================
def create_default_notification_templates():
    """
    Create default notification templates if they don't exist
    Run this in a migration or management command
    """
    templates = [
        {
            'name': 'Demo Confirmation',
            'notification_type': 'demo_confirmation',
            'email_subject': 'Demo Session Confirmed - {{demo_title}}',
            'email_body': '''
                <p>Dear {{user_name}},</p>
                <p>Your demo session for <strong>{{demo_title}}</strong> has been confirmed.</p>
                <p><strong>Date:</strong> {{requested_date}}<br>
                <strong>Time:</strong> {{time_slot}}</p>
                <p>We look forward to meeting with you.</p>
                <p>Best regards,<br>CHRP India Team</p>
            ''',
            'title_template': 'Demo Confirmed: {{demo_title}}',
            'message_template': 'Your demo for {{demo_title}} is confirmed for {{requested_date}} at {{time_slot}}',
        },
        {
            'name': 'Demo Reschedule',
            'notification_type': 'demo_reschedule',
            'email_subject': 'Demo Session Rescheduled - {{demo_title}}',
            'email_body': '''
                <p>Dear {{user_name}},</p>
                <p>Your demo session for <strong>{{demo_title}}</strong> has been rescheduled.</p>
                <p><strong>New Date:</strong> {{new_date}}<br>
                <strong>New Time:</strong> {{time_slot}}</p>
                <p>Previous date was: {{old_date}}</p>
                <p>We apologize for any inconvenience.</p>
                <p>Best regards,<br>CHRP India Team</p>
            ''',
            'title_template': 'Demo Rescheduled: {{demo_title}}',
            'message_template': 'Your demo has been rescheduled from {{old_date}} to {{new_date}} at {{time_slot}}',
        },
        {
            'name': 'Demo Cancellation',
            'notification_type': 'demo_cancellation',
            'email_subject': 'Demo Session Cancelled - {{demo_title}}',
            'email_body': '''
                <p>Dear {{user_name}},</p>
                <p>Your demo session for <strong>{{demo_title}}</strong> scheduled on {{cancelled_date}} has been cancelled.</p>
                <p><strong>Reason:</strong> {{reason}}</p>
                <p>Please feel free to schedule another demo at your convenience.</p>
                <p>Best regards,<br>CHRP India Team</p>
            ''',
            'title_template': 'Demo Cancelled: {{demo_title}}',
            'message_template': 'Your demo for {{demo_title}} on {{cancelled_date}} has been cancelled. Reason: {{reason}}',
        },
        {
            'name': 'Enquiry Received',
            'notification_type': 'enquiry_received',
            'email_subject': 'Enquiry Received - {{enquiry_id}}',
            'email_body': '''
                <p>Dear {{user_name}},</p>
                <p>Thank you for your business enquiry.</p>
                <p><strong>Enquiry ID:</strong> {{enquiry_id}}<br>
                <strong>Subject:</strong> {{subject}}<br>
                <strong>Organization:</strong> {{organization}}</p>
                <p>Our team will review and respond within 24 hours.</p>
                <p>Best regards,<br>CHRP India Team</p>
            ''',
            'title_template': 'Enquiry Received: {{enquiry_id}}',
            'message_template': 'Your enquiry {{enquiry_id}} has been received. We will respond within 24 hours.',
        },
        {
            'name': 'Enquiry Response',
            'notification_type': 'enquiry_response',
            'email_subject': 'Response to Your Enquiry - {{enquiry_id}}',
            'email_body': '''
                <p>Dear {{user_name}},</p>
                <p>We have responded to your enquiry (ID: {{enquiry_id}}).</p>
                <p><strong>Response Summary:</strong><br>{{response_summary}}</p>
                <p>Please check your dashboard for full details.</p>
                <p>Best regards,<br>CHRP India Team</p>
            ''',
            'title_template': 'Enquiry Answered: {{enquiry_id}}',
            'message_template': 'Your enquiry {{enquiry_id}} has been answered. {{response_summary}}',
        },
        {
            'name': 'New Demo Available',
            'notification_type': 'new_demo_available',
            'email_subject': 'New Demo Available - {{demo_title}}',
            'email_body': '''
                <p>Dear Customer,</p>
                <p>A new demo is now available for viewing.</p>
                <p><strong>Title:</strong> {{demo_title}}<br>
                <strong>Category:</strong> {{category}}<br>
                <strong>Duration:</strong> {{duration}}</p>
                <p>Login to your dashboard to watch this demo.</p>
                <p>Best regards,<br>CHRP India Team</p>
            ''',
            'title_template': 'New Demo: {{demo_title}}',
            'message_template': 'New demo available: {{demo_title}} in {{category}} category ({{duration}})',
        },
        {
            'name': 'Account Approved',
            'notification_type': 'account_approved',
            'email_subject': 'Welcome! Your Account is Approved',
            'email_body': '''
                <p>Dear {{user_name}},</p>
                <p>Great news! Your account has been approved on {{approval_date}}.</p>
                <p>You now have full access to:</p>
                <ul>
                    <li>View all demo videos</li>
                    <li>Request live demo sessions</li>
                    <li>Submit business enquiries</li>
                    <li>Access exclusive content</li>
                </ul>
                <p>Login now to explore our demo portal.</p>
                <p>Best regards,<br>CHRP India Team</p>
            ''',
            'title_template': 'Account Approved! Welcome to CHRP India',
            'message_template': 'Your account has been approved on {{approval_date}}. You now have full access to the portal.',
        },
        {
            'name': 'System Announcement',
            'notification_type': 'system_announcement',
            'email_subject': '{{title}}',
            'email_body': '''
                <p>Dear User,</p>
                <p><strong>{{title}}</strong></p>
                <p>{{message}}</p>
                <p>Priority: {{priority}}</p>
                <p>Best regards,<br>CHRP India Team</p>
            ''',
            'title_template': '{{title}}',
            'message_template': '{{message}}',
        },
    ]
    
    for template_data in templates:
        NotificationTemplate.objects.get_or_create(
            notification_type=template_data['notification_type'],
            defaults=template_data
        )
    
    return f"Created/updated {len(templates)} notification templates"


# =========================================
# Management Command Helper
# =========================================
def initialize_notification_system():
    """
    Complete initialization of notification system
    Call this in manage.py shell or create a management command
    """
    result = create_default_notification_templates()
    print(result)
    print("Notification system initialized successfully!")
    return True