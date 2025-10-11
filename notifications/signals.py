# notifications/signals.py
"""
Django signals for automatic notification creation
Triggers notifications when models change
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


# Import here to avoid circular imports
def get_notification_service():
    """Lazy import to avoid circular dependency"""
    from .services import NotificationService
    return NotificationService


# ============================================
# User Signals
# ============================================

@receiver(pre_save, sender='accounts.CustomUser')
def store_old_user_approval(sender, instance, **kwargs):
    """Store old approval status before save"""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_is_approved = old.is_approved
        except sender.DoesNotExist:
            instance._old_is_approved = False


@receiver(post_save, sender='accounts.CustomUser')
def notify_user_approval(sender, instance, created, **kwargs):
    """Notify user when account approved"""
    if not created and instance.is_approved:
        if hasattr(instance, '_old_is_approved'):
            if not instance._old_is_approved and instance.is_approved:
                NotificationService = get_notification_service()
                NotificationService.notify_account_approved(instance)
                logger.info(f"Sent approval notification to {instance.email}")


@receiver(post_save, sender='accounts.CustomUser')
def notify_admin_new_customer(sender, instance, created, **kwargs):
    """Notify admins about new customer"""
    if created and not instance.is_staff:
        NotificationService = get_notification_service()
        NotificationService.notify_admin_new_customer(instance)


# ============================================
# Demo Request Signals
# ============================================

@receiver(pre_save, sender='demos.DemoRequest')
def store_old_demo_request_status(sender, instance, **kwargs):
    """Store old status before save"""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_status = old.status
            instance._old_date = old.confirmed_date or old.requested_date
            instance._old_slot = old.confirmed_time_slot or old.requested_time_slot
        except sender.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender='demos.DemoRequest')
def notify_demo_request_changes(sender, instance, created, **kwargs):
    """Notify on demo request status changes"""
    NotificationService = get_notification_service()
    
    # Notify admin on new request
    if created:
        NotificationService.notify_admin_new_demo_request(instance)
        return
    
    # Notify customer on status change
    if hasattr(instance, '_old_status'):
        old_status = instance._old_status
        new_status = instance.status
        
        if old_status != new_status:
            if new_status == 'confirmed':
                NotificationService.notify_demo_request_confirmed(instance)
            elif new_status == 'cancelled':
                NotificationService.notify_demo_request_cancelled(instance)
            elif new_status == 'rescheduled':
                NotificationService.notify_demo_request_rescheduled(
                    instance,
                    instance._old_date,
                    instance._old_slot
                )


# ============================================
# Enquiry Signals
# ============================================

@receiver(pre_save, sender='enquiries.BusinessEnquiry')
def store_old_enquiry_status(sender, instance, **kwargs):
    """Store old status before save"""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except sender.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender='enquiries.BusinessEnquiry')
def notify_enquiry_changes(sender, instance, created, **kwargs):
    """Notify on enquiry changes"""
    NotificationService = get_notification_service()
    
    # Confirmation on new enquiry
    if created:
        NotificationService.notify_enquiry_received(instance)
        NotificationService.notify_admin_new_enquiry(instance)
        return
    
    # Notify on status change to answered
    if hasattr(instance, '_old_status'):
        old_status = instance._old_status
        new_status = instance.status
        
        if old_status != new_status and new_status == 'answered':
            NotificationService.notify_enquiry_response(instance)


# ============================================
# Demo Signals
# ============================================

@receiver(post_save, sender='demos.Demo')
def notify_new_demo(sender, instance, created, **kwargs):
    """Notify users about new demo"""
    if created and instance.is_active:
        NotificationService = get_notification_service()
        NotificationService.notify_new_demo_available(instance)
        logger.info(f"Sent new demo notifications for {instance.title}")


@receiver(pre_save, sender='accounts.CustomUser')
def store_old_block_status(sender, instance, **kwargs):
    """Store old block status"""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_is_blocked = old.is_blocked if hasattr(old, 'is_blocked') else False
        except sender.DoesNotExist:
            instance._old_is_blocked = False


@receiver(post_save, sender='accounts.CustomUser')
def notify_block_status_change(sender, instance, created, **kwargs):
    """Notify on block/unblock"""
    if not created and not instance.is_staff:
        if hasattr(instance, '_old_is_blocked'):
            old_blocked = instance._old_is_blocked
            new_blocked = instance.is_blocked if hasattr(instance, 'is_blocked') else False
            
            if old_blocked != new_blocked:
                from notifications.services import NotificationService
                if new_blocked:
                    NotificationService.notify_account_blocked(instance)
                else:
                    NotificationService.notify_account_unblocked(instance)


# ============================================
# Demo Request Rejection Signal
# ============================================

@receiver(post_save, sender='demos.DemoRequest')
def notify_demo_rejection(sender, instance, created, **kwargs):
    """Notify on demo request rejection"""
    if not created:
        if hasattr(instance, '_old_status'):
            old_status = instance._old_status
            new_status = instance.status
            
            if old_status != new_status and new_status == 'rejected':
                from notifications.services import NotificationService
                reason = instance.admin_notes or 'Not available for requested date'
                NotificationService.notify_demo_request_rejected(instance, reason)


# ============================================
# Enquiry Status Change Signal
# ============================================

@receiver(post_save, sender='enquiries.BusinessEnquiry')
def notify_enquiry_status_change(sender, instance, created, **kwargs):
    """Notify on enquiry status changes (all statuses)"""
    if not created:
        if hasattr(instance, '_old_status'):
            old_status = instance._old_status
            new_status = instance.status
            
            if old_status != new_status:
                from notifications.services import NotificationService
                
                # Send notification for any status change
                if new_status in ['in_progress', 'pending']:
                    NotificationService.notify_enquiry_status_change(
                        instance, old_status, new_status
                    )        




@receiver(post_save, sender='demos.DemoRequest')
def notify_admin_on_customer_cancellation(sender, instance, created, **kwargs):
    """
    Notify admins when customer cancels a demo request
    This is a backup in case the view doesn't trigger the notification
    """
    if not created and hasattr(instance, '_old_status'):
        old_status = instance._old_status
        new_status = instance.status
        
        # Check if status changed to cancelled
        if old_status != 'cancelled' and new_status == 'cancelled':
            # Check if cancelled by customer (has cancellation_reason)
            if instance.cancellation_reason:
                from notifications.services import NotificationService
                try:
                    NotificationService.notify_admin_demo_request_cancelled(
                        demo_request=instance,
                        cancelled_by_customer=True,
                        send_email=True
                    )
                    logger.info(f"✅ Admin notified of customer cancellation for request #{instance.id}")
                except Exception as e:
                    logger.error(f"❌ Error notifying admin of cancellation: {e}")


