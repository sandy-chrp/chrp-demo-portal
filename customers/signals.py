# customers/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.auth import get_user_model
from django.utils import timezone

# Import models (only import what exists)
User = get_user_model()

# Only import demo models if they exist
try:
    from demos.models import DemoView, DemoLike, DemoRequest
    DEMOS_AVAILABLE = True
except ImportError:
    DEMOS_AVAILABLE = False

# Only import enquiry models if they exist
try:
    from enquiries.models import BusinessEnquiry
    ENQUIRIES_AVAILABLE = True
except ImportError:
    ENQUIRIES_AVAILABLE = False

# Import our customer models
from .models import CustomerActivity, SecurityViolation
from .utils import log_customer_activity, send_security_alert

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log customer login activity"""
    if hasattr(user, 'is_approved') and user.is_approved:
        log_customer_activity(
            user=user,
            activity_type='login',
            description=f'Customer logged in from {request.META.get("REMOTE_ADDR", "unknown")}',
            request=request
        )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log customer logout activity"""
    if user and hasattr(user, 'is_approved') and user.is_approved:
        log_customer_activity(
            user=user,
            activity_type='logout',
            description='Customer logged out',
            request=request
        )

# Only register demo signals if demos app is available
if DEMOS_AVAILABLE:
    @receiver(post_save, sender=DemoView)
    def log_demo_view(sender, instance, created, **kwargs):
        """Log demo view activity"""
        if created:
            log_customer_activity(
                user=instance.user,
                activity_type='demo_view',
                description=f'Viewed demo: {instance.demo.title}',
                demo_id=instance.demo.id,
                demo_title=instance.demo.title
            )

    @receiver(post_save, sender=DemoLike)
    def log_demo_like(sender, instance, created, **kwargs):
        """Log demo like activity"""
        if created:
            log_customer_activity(
                user=instance.user,
                activity_type='demo_like',
                description=f'Liked demo: {instance.demo.title}',
                demo_id=instance.demo.id,
                demo_title=instance.demo.title
            )

    @receiver(post_save, sender=DemoRequest)
    def log_demo_request(sender, instance, created, **kwargs):
        """Log demo request activity"""
        if created:
            log_customer_activity(
                user=instance.user,
                activity_type='demo_request',
                description=f'Requested demo: {instance.demo.title} for {instance.requested_date}',
                demo_id=instance.demo.id,
                demo_title=instance.demo.title,
                requested_date=str(instance.requested_date)
            )

# Only register enquiry signals if enquiries app is available
if ENQUIRIES_AVAILABLE:
    @receiver(post_save, sender=BusinessEnquiry)
    def log_enquiry_sent(sender, instance, created, **kwargs):
        """Log business enquiry activity"""
        if created:
            log_customer_activity(
                user=instance.user,
                activity_type='enquiry_sent',
                description=f'Sent enquiry: {instance.enquiry_id}',
                enquiry_id=instance.enquiry_id,
                subject=instance.subject or 'No subject'
            )

@receiver(post_save, sender=SecurityViolation)
def handle_security_violation(sender, instance, created, **kwargs):
    """Handle security violation detection"""
    if created:
        # Log as customer activity
        log_customer_activity(
            user=instance.user,
            activity_type='security_violation',
            description=f'Security violation: {instance.get_violation_type_display()}',
            violation_type=instance.violation_type,
            violation_description=instance.description
        )
        
        # Send alert for serious violations
        serious_violations = [
            'screen_recording',
            'multiple_sessions',
            'devtools_detected'
        ]
        
        if instance.violation_type in serious_violations:
            send_security_alert(
                user=instance.user,
                violation_type=instance.get_violation_type_display(),
                description=instance.description
            )
        
        # Auto-suspend user for repeated violations
        violation_count = SecurityViolation.objects.filter(
            user=instance.user,
            created_at__date=instance.created_at.date()
        ).count()
        
        if violation_count >= 10:  # More than 10 violations in a day
            instance.user.is_active = False
            instance.user.save()
            
            # Send suspension alert
            send_security_alert(
                user=instance.user,
                violation_type='Account Suspended',
                description=f'User suspended due to {violation_count} security violations in one day'
            )