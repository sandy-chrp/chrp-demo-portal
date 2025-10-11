# notifications/services.py
"""
Notification Service - Business logic for notifications
Handles creation, sending emails, and managing notifications
"""

from django.utils import timezone
from django.template import Template, Context
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from .models import Notification, NotificationTemplate
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """Service class for all notification operations"""
    
    @staticmethod
    def send_email_notification(user, subject, template_name, context=None):
        """
        Send HTML email notification
        
        Args:
            user: User object to send email to
            subject: Email subject line
            template_name: Name of the email template (without .html)
            context: Dictionary of context variables for the template
        """
        if not user.email:
            logger.warning(f"User {user.id} has no email address")
            return False
        
        try:
            # Prepare context
            email_context = {
                'user': user,
                'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
                'site_name': getattr(settings, 'SITE_NAME', 'Demo Portal'),
            }
            if context:
                email_context.update(context)
            
            # Render HTML email
            html_content = render_to_string(
                f'emails/{template_name}.html',
                email_context
            )
            
            # Create plain text version (strip HTML tags)
            text_content = strip_tags(html_content)
            
            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@demoportal.com'),
                to=[user.email]
            )
            
            # Attach HTML version
            email.attach_alternative(html_content, "text/html")
            
            # Send email
            email.send(fail_silently=False)
            
            logger.info(f"✅ Email sent to {user.email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending email to {user.email}: {str(e)}")
            return False
    
    @staticmethod
    def create_notification(user, notification_type, context_data=None, related_object=None, send_email=True):
        """
        Create notification from template
        
        Args:
            user: User object
            notification_type: Type from NotificationTemplate.NOTIFICATION_TYPES
            context_data: Dict with template variables
            related_object: Related model instance (optional)
            send_email: Whether to send email notification
        
        Returns:
            Notification instance or None
        """
        try:
            # Get template
            template = NotificationTemplate.objects.filter(
                notification_type=notification_type,
                is_active=True
            ).first()
            
            if not template:
                logger.warning(f"No template found for {notification_type}")
                return None
            
            # Render content
            context = Context(context_data or {})
            title = Template(template.title_template).render(context)
            message = Template(template.message_template).render(context)
            
            # Create notification
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title,
                message=message,
                content_object=related_object
            )
            
            # Send email if enabled
            if send_email and template.send_email:
                NotificationService._send_email_from_template(user, template, context_data, notification)
            
            logger.info(f"✅ Created notification {notification.id} for {user.email}")
            return notification
            
        except Exception as e:
            logger.error(f"❌ Error creating notification: {e}")
            return None
    
    @staticmethod
    def _send_email_from_template(user, template, context_data, notification):
        """Internal method to send email from template"""
        try:
            context = Context(context_data or {})
            subject = Template(template.email_subject).render(context) if template.email_subject else template.title_template
            body = Template(template.email_body).render(context) if template.email_body else template.message_template
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=strip_tags(body),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@demoportal.com'),
                to=[user.email]
            )
            
            email.attach_alternative(body, "text/html")
            email.send(fail_silently=False)
            
            notification.email_sent = True
            notification.email_sent_at = timezone.now()
            notification.save(update_fields=['email_sent', 'email_sent_at'])
            
            logger.info(f"✅ Email sent to {user.email}")
            
        except Exception as e:
            notification.email_error = str(e)
            notification.save(update_fields=['email_error'])
            logger.error(f"❌ Email error: {e}")
    
    # ============================================
    # Customer Notification Methods (with Email)
    # ============================================
    
    @staticmethod
    def notify_account_approved(user, send_email=True):
        """Customer account approved"""
        # Create notification
        notification = Notification.objects.create(
            user=user,
            title='Account Approved',
            message='Your account has been approved! You now have full access to our demo library.',
            notification_type='account_approved'
        )
        
        # Send email
        if send_email:
            NotificationService.send_email_notification(
                user=user,
                subject='🎉 Your Demo Portal Account is Approved!',
                template_name='account_approved'
            )
        
        return notification
    
    @staticmethod
    def notify_account_blocked(user, reason='Policy violation', send_email=True):
        """Account blocked notification"""
        notification = Notification.objects.create(
            user=user,
            title='Account Blocked',
            message=f'Your account has been blocked. Reason: {reason}',
            notification_type='account_blocked'
        )
        
        if send_email:
            context = {
                'reason': reason,
                'blocked_date': timezone.now().strftime('%B %d, %Y'),
            }
            NotificationService.send_email_notification(
                user=user,
                subject='Account Blocked - Demo Portal',
                template_name='account_blocked',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_account_unblocked(user, send_email=True):
        """Account unblocked notification"""
        notification = Notification.objects.create(
            user=user,
            title='Account Unblocked',
            message='Your account has been unblocked. You can now access Demo Portal.',
            notification_type='account_unblocked'
        )
        
        if send_email:
            NotificationService.send_email_notification(
                user=user,
                subject='Account Unblocked - Demo Portal',
                template_name='account_unblocked'
            )
        
        return notification
    
    @staticmethod
    def notify_demo_request_confirmed(demo_request, send_email=True):
        """Demo request confirmed"""
        notification = Notification.objects.create(
            user=demo_request.user,
            title='Demo Request Confirmed',
            message=f'Your demo request for "{demo_request.demo.title}" has been confirmed.',
            notification_type='demo_confirmation',
            content_object=demo_request
        )
        
        if send_email:
            context = {
                'demo_title': demo_request.demo.title,
                'request_date': demo_request.created_at.strftime('%B %d, %Y'),
                'preferred_date': demo_request.requested_date.strftime('%B %d, %Y') if hasattr(demo_request, 'requested_date') else 'TBD',
            }
            NotificationService.send_email_notification(
                user=demo_request.user,
                subject=f'✓ Demo Request Confirmed - {demo_request.demo.title}',
                template_name='demo_confirmed',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_demo_request_rejected(demo_request, reason='Not available', send_email=True):
        """Demo request rejected"""
        notification = Notification.objects.create(
            user=demo_request.user,
            title='Demo Request Rejected',
            message=f'Your demo request for "{demo_request.demo.title}" has been rejected. Reason: {reason}',
            notification_type='demo_rejection',
            content_object=demo_request
        )
        
        if send_email:
            context = {
                'demo_title': demo_request.demo.title,
                'reason': reason,
                'request_date': demo_request.created_at.strftime('%B %d, %Y'),
            }
            NotificationService.send_email_notification(
                user=demo_request.user,
                subject=f'Demo Request Update - {demo_request.demo.title}',
                template_name='demo_rejected',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_demo_request_rescheduled(demo_request, old_date, old_slot, send_email=True):
        """Demo request rescheduled"""
        notification = Notification.objects.create(
            user=demo_request.user,
            title='Demo Request Rescheduled',
            message=f'Your demo for "{demo_request.demo.title}" has been rescheduled.',
            notification_type='demo_reschedule',
            content_object=demo_request
        )
        
        if send_email:
            context = {
                'demo_title': demo_request.demo.title,
                'old_date': old_date.strftime('%B %d, %Y') if old_date else 'Previous date',
                'new_date': demo_request.requested_date.strftime('%B %d, %Y') if hasattr(demo_request, 'requested_date') else 'New date',
            }
            NotificationService.send_email_notification(
                user=demo_request.user,
                subject=f'Demo Rescheduled - {demo_request.demo.title}',
                template_name='demo_rescheduled',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_demo_request_cancelled(demo_request, reason='', send_email=True):
        """Demo request cancelled"""
        notification = Notification.objects.create(
            user=demo_request.user,
            title='Demo Request Cancelled',
            message=f'Your demo request for "{demo_request.demo.title}" has been cancelled.',
            notification_type='demo_cancellation',
            content_object=demo_request
        )
        
        if send_email:
            context = {
                'demo_title': demo_request.demo.title,
                'reason': reason or 'No reason provided',
            }
            NotificationService.send_email_notification(
                user=demo_request.user,
                subject=f'Demo Cancelled - {demo_request.demo.title}',
                template_name='demo_cancelled',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_enquiry_received(enquiry, send_email=True):
        """Enquiry received confirmation"""
        notification = Notification.objects.create(
            user=enquiry.user,
            title='Enquiry Received',
            message=f'We have received your enquiry. ID: {enquiry.enquiry_id if hasattr(enquiry, "enquiry_id") else enquiry.id}',
            notification_type='enquiry_received',
            content_object=enquiry
        )
        
        if send_email:
            context = {
                'enquiry_id': enquiry.enquiry_id if hasattr(enquiry, 'enquiry_id') else enquiry.id,
                'subject': getattr(enquiry, 'subject', 'Business Enquiry'),
                'enquiry_date': enquiry.created_at.strftime('%B %d, %Y'),
            }
            NotificationService.send_email_notification(
                user=enquiry.user,
                subject='✓ Enquiry Received - We\'ll Get Back to You Soon',
                template_name='enquiry_received',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_enquiry_response(enquiry, response_summary='', send_email=True):
        """Enquiry answered"""
        notification = Notification.objects.create(
            user=enquiry.user,
            title='Enquiry Response',
            message=f'Your enquiry has been answered. Please check your enquiry dashboard.',
            notification_type='enquiry_response',
            content_object=enquiry
        )
        
        if send_email:
            context = {
                'enquiry_id': enquiry.enquiry_id if hasattr(enquiry, 'enquiry_id') else enquiry.id,
                'response_summary': response_summary[:200] if response_summary else 'Your enquiry has been answered.',
            }
            NotificationService.send_email_notification(
                user=enquiry.user,
                subject='✓ Response to Your Enquiry',
                template_name='enquiry_response',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_enquiry_status_change(enquiry, old_status, new_status, send_email=True):
        """Enquiry status changed"""
        notification = Notification.objects.create(
            user=enquiry.user,
            title='Enquiry Status Updated',
            message=f'Your enquiry status changed from {old_status} to {new_status}.',
            notification_type='enquiry_status',
            content_object=enquiry
        )
        
        if send_email:
            context = {
                'enquiry_id': enquiry.enquiry_id if hasattr(enquiry, 'enquiry_id') else enquiry.id,
                'old_status': old_status.upper(),
                'new_status': new_status.upper(),
            }
            NotificationService.send_email_notification(
                user=enquiry.user,
                subject=f'Enquiry Status Update - {new_status.upper()}',
                template_name='enquiry_status_update',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_new_demo_available(demo, send_email=True):
        """New demo available - bulk notification"""
        from accounts.models import CustomUser
        
        # Get target users
        users = CustomUser.objects.filter(is_active=True, is_staff=False)
        
        notifications = []
        for user in users:
            notification = Notification.objects.create(
                user=user,
                title='New Demo Available',
                message=f'A new demo "{demo.title}" is now available!',
                notification_type='new_demo_available',
                content_object=demo
            )
            notifications.append(notification)
            
            if send_email:
                context = {
                    'demo_title': demo.title,
                    'category': getattr(demo, 'category', 'General'),
                }
                NotificationService.send_email_notification(
                    user=user,
                    subject=f'🎯 New Demo: {demo.title}',
                    template_name='new_demo_available',
                    context=context
                )
        
        return notifications
    
    @staticmethod
    def notify_password_reset(user, reset_link, ip_address='Unknown', send_email=True):
        """Password reset notification"""
        notification = Notification.objects.create(
            user=user,
            title='Password Reset Request',
            message='A password reset was requested for your account.',
            notification_type='password_reset'
        )
        
        if send_email:
            context = {
                'reset_link': reset_link,
                'ip_address': ip_address,
                'request_time': timezone.now().strftime('%B %d, %Y %I:%M %p'),
            }
            NotificationService.send_email_notification(
                user=user,
                subject='Password Reset Request - Demo Portal',
                template_name='password_reset',
                context=context
            )
        
        return notification
    
    @staticmethod
    def notify_profile_updated(user, updated_fields, send_email=True):
        """Profile updated notification"""
        notification = Notification.objects.create(
            user=user,
            title='Profile Updated',
            message=f'Your profile has been updated. Fields changed: {", ".join(updated_fields)}',
            notification_type='profile_updated'
        )
        
        if send_email:
            context = {
                'updated_fields': ', '.join(updated_fields),
                'update_time': timezone.now().strftime('%B %d, %Y %I:%M %p'),
            }
            NotificationService.send_email_notification(
                user=user,
                subject='Profile Updated - Demo Portal',
                template_name='profile_updated',
                context=context
            )
        
        return notification
    
    # ============================================
    # Admin Notification Methods (with Email)
    # ============================================
    
    @staticmethod
    def notify_admin_new_customer(customer, send_email=True):
        """Notify admins about new customer registration"""
        from accounts.models import CustomUser
        
        admins = CustomUser.objects.filter(is_staff=True, is_active=True)
        
        notifications = []
        for admin in admins:
            notification = Notification.objects.create(
                user=admin,
                title='New Customer Registration',
                message=f'{customer.get_full_name()} ({customer.email}) has registered and needs approval.',
                notification_type='new_customer',
                content_object=customer
            )
            notifications.append(notification)
            
            if send_email:
                context = {
                    'customer_name': customer.get_full_name(),
                    'customer_email': customer.email,
                    'customer_company': getattr(customer, 'company_name', 'N/A'),
                    'registration_date': customer.date_joined.strftime('%B %d, %Y at %I:%M %p'),
                }
                NotificationService.send_email_notification(
                    user=admin,
                    subject=f'🆕 New Customer Registration - {customer.get_full_name()}',
                    template_name='admin_new_customer',
                    context=context
                )
        
        return notifications
    
    @staticmethod
    def notify_admin_new_demo_request(demo_request, send_email=True):
        """Notify admins about new demo request"""
        from accounts.models import CustomUser
        
        admins = CustomUser.objects.filter(is_staff=True, is_active=True)
        
        notifications = []
        for admin in admins:
            notification = Notification.objects.create(
                user=admin,
                title='New Demo Request',
                message=f'{demo_request.user.get_full_name()} requested demo for {demo_request.demo.title}',
                notification_type='demo_request',
                content_object=demo_request
            )
            notifications.append(notification)
            
            if send_email:
                context = {
                    'customer_name': demo_request.user.get_full_name(),
                    'demo_title': demo_request.demo.title,
                    'request_date': demo_request.created_at.strftime('%B %d, %Y'),
                }
                NotificationService.send_email_notification(
                    user=admin,
                    subject=f'🎯 New Demo Request - {demo_request.demo.title}',
                    template_name='admin_new_demo_request',
                    context=context
                )
        
        return notifications
    
    @staticmethod
    def notify_admin_new_enquiry(enquiry, send_email=True):
        """Notify admins about new enquiry"""
        from accounts.models import CustomUser
        
        admins = CustomUser.objects.filter(is_staff=True, is_active=True)
        
        notifications = []
        for admin in admins:
            enquiry_id = enquiry.enquiry_id if hasattr(enquiry, 'enquiry_id') else enquiry.id
            notification = Notification.objects.create(
                user=admin,
                title='New Business Enquiry',
                message=f'New enquiry from {enquiry.user.get_full_name()} - ID: {enquiry_id}',
                notification_type='enquiry',
                content_object=enquiry
            )
            notifications.append(notification)
            
            if send_email:
                context = {
                    'customer_name': enquiry.user.get_full_name(),
                    'enquiry_id': enquiry_id,
                    'subject': getattr(enquiry, 'subject', 'Business Enquiry'),
                    'enquiry_date': enquiry.created_at.strftime('%B %d, %Y'),
                }
                NotificationService.send_email_notification(
                    user=admin,
                    subject=f'💬 New Enquiry - {enquiry_id}',
                    template_name='admin_new_enquiry',
                    context=context
                )
        
        return notifications
    
    @staticmethod
    def send_custom_notification(user, title, message, notification_type='system_announcement', link=None, send_email=False, email_subject=None):
        """
        Send a custom notification (for bulk sending)
        
        Args:
            user: User object
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            link: Optional link
            send_email: Whether to send email
            email_subject: Custom email subject
        """
        # Create notification
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type
        )
        
        # Send email if requested
        if send_email:
            context = {
                'title': title,
                'message': message,
                'link': link,
            }
            
            NotificationService.send_email_notification(
                user=user,
                subject=email_subject or title,
                template_name='custom_notification',
                context=context
            )
        
        return notification
    
    # ============================================
    # Utility Methods
    # ============================================
    
    @staticmethod
    def get_unread_count(user):
        """Get unread notification count for user"""
        return Notification.objects.filter(user=user, is_read=False).count()
    
    @staticmethod
    def mark_as_read(notification_id, user):
        """Mark specific notification as read"""
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=['is_read', 'read_at'])
            return True
        except Notification.DoesNotExist:
            return False
    
    @staticmethod
    def mark_all_as_read(user):
        """Mark all user notifications as read"""
        return Notification.objects.filter(
            user=user,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
    
    @staticmethod
    def get_recent_notifications(user, limit=10):
        """Get recent notifications for user"""
        return Notification.objects.filter(user=user).order_by('-created_at')[:limit]
    
    @staticmethod
    def delete_old_notifications(days=90):
        """Clean up old read notifications"""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return Notification.objects.filter(
            created_at__lt=cutoff,
            is_read=True
        ).delete()
    

@staticmethod
def notify_admin_demo_request_cancelled(demo_request, cancelled_by_customer=True, send_email=True):
    """
    Notify admins when a demo request is cancelled by customer
    
    Args:
        demo_request: DemoRequest instance
        cancelled_by_customer: Boolean - True if customer cancelled, False if admin cancelled
        send_email: Whether to send email notification
    """
    from accounts.models import CustomUser
    
    # Get all active admins
    admins = CustomUser.objects.filter(is_staff=True, is_active=True)
    
    # Get cancellation details
    cancellation_reason = demo_request.get_cancellation_reason_display() if demo_request.cancellation_reason else 'No reason provided'
    cancellation_details = demo_request.cancellation_details or 'No additional details'
    
    notifications = []
    for admin in admins:
        # Create notification
        if cancelled_by_customer:
            title = f'Demo Request Cancelled by Customer'
            message = (
                f'{demo_request.user.get_full_name()} cancelled their demo request for '
                f'"{demo_request.demo.title}". Reason: {cancellation_reason}'
            )
        else:
            title = f'Demo Request Cancelled'
            message = (
                f'Demo request for "{demo_request.demo.title}" by {demo_request.user.get_full_name()} '
                f'has been cancelled.'
            )
        
        notification = Notification.objects.create(
            user=admin,
            title=title,
            message=message,
            notification_type='demo_cancellation',
            content_object=demo_request
        )
        notifications.append(notification)
        
        # Send email if enabled
        if send_email:
            context = {
                'admin_name': admin.get_full_name() or 'Admin',
                'customer_name': demo_request.user.get_full_name(),
                'customer_email': demo_request.user.email,
                'demo_title': demo_request.demo.title,
                'request_id': demo_request.id,
                'requested_date': demo_request.requested_date.strftime('%B %d, %Y'),
                'requested_time': demo_request.requested_time_slot.start_time.strftime('%I:%M %p'),
                'cancellation_reason': cancellation_reason,
                'cancellation_details': cancellation_details,
                'cancelled_at': demo_request.cancelled_at.strftime('%B %d, %Y at %I:%M %p') if demo_request.cancelled_at else 'Recently',
                'cancelled_by': 'Customer' if cancelled_by_customer else 'Admin',
            }
            
            NotificationService.send_email_notification(
                user=admin,
                subject=f'🚫 Demo Cancelled - {demo_request.demo.title}',
                template_name='admin_demo_cancelled',
                context=context
            )
    
    logger.info(f"✅ Sent cancellation notifications to {len(notifications)} admins for request #{demo_request.id}")
    return notifications

