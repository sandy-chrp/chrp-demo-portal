# customers/utils.py
# SIMPLIFIED VERSION - No email template required

from django.core.mail import send_mail
from django.conf import settings
from .models import CustomerActivity, SecurityViolation

def log_customer_activity(user, activity_type, description, request=None, **metadata):
    """Log customer activity for tracking"""
    ip_address = '127.0.0.1'
    user_agent = ''
    
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    try:
        CustomerActivity.objects.create(
            user=user,
            activity_type=activity_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata
        )
    except Exception as e:
        print(f"⚠️ Activity logging error: {e}")

def log_security_violation(user, violation_type, description, request=None):
    """Log security violation"""
    ip_address = '127.0.0.1'
    user_agent = ''
    page_url = ''
    referrer = ''
    
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        page_url = request.build_absolute_uri()
        referrer = request.META.get('HTTP_REFERER', '')
    
    try:
        SecurityViolation.objects.create(
            user=user,
            violation_type=violation_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            page_url=page_url,
            referrer=referrer,
        )
    except Exception as e:
        print(f"⚠️ Security violation logging error: {e}")

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def send_security_alert(user, violation_type, description):
    """
    Send security alert email to admin
    ✅ SIMPLIFIED - No template required
    """
    try:
        subject = f"Security Alert - {violation_type}"
        
        # Simple text email instead of HTML template
        message = f"""
Security Alert - Demo Portal

User: {user.email} ({user.get_full_name()})
Violation Type: {violation_type}
Description: {description}
Time: {timezone.now()}

Please review this security incident in the admin panel.
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.DEFAULT_FROM_EMAIL],
            fail_silently=True,
        )
    except Exception as e:
        print(f"⚠️ Email sending error: {e}")

def check_user_permissions(user, demo):
    """Check if user can access specific demo"""
    if not user.is_authenticated or not user.is_approved:
        return False
    
    if demo.target_customers.exists():
        return demo.target_customers.filter(id=user.id).exists()
    
    return True

def sanitize_user_input(text):
    """Sanitize user input for security"""
    import re
    
    dangerous_patterns = [
        r'<script.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'<iframe.*?</iframe>',
    ]
    
    cleaned_text = text
    for pattern in dangerous_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
    
    return cleaned_text.strip()