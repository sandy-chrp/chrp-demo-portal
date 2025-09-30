# customers/utils.py - Utility functions for customer portal
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import CustomerActivity, SecurityViolation

def log_customer_activity(user, activity_type, description, request=None, **metadata):
    """Log customer activity for tracking"""
    ip_address = '127.0.0.1'
    user_agent = ''
    
    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    CustomerActivity.objects.create(
        user=user,
        activity_type=activity_type,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata
    )

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
    
    SecurityViolation.objects.create(
        user=user,
        violation_type=violation_type,
        description=description,
        ip_address=ip_address,
        user_agent=user_agent,
        page_url=page_url,
        referrer=referrer,
    )

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def send_security_alert(user, violation_type, description):
    """Send security alert email to admin"""
    subject = f"Security Alert - {violation_type}"
    message = render_to_string('emails/security_alert.html', {
        'user': user,
        'violation_type': violation_type,
        'description': description,
    })
    
    send_mail(
        subject,
        '',
        settings.DEFAULT_FROM_EMAIL,
        [settings.DEFAULT_FROM_EMAIL],  # Send to admin
        html_message=message,
        fail_silently=True,
    )

def check_user_permissions(user, demo):
    """Check if user can access specific demo"""
    if not user.is_authenticated or not user.is_approved:
        return False
    
    # Check if demo allows all customers or specifically targets this user
    if demo.target_customers.exists():
        return demo.target_customers.filter(id=user.id).exists()
    
    return True

def sanitize_user_input(text):
    """Sanitize user input for security"""
    import re
    
    # Remove potentially dangerous patterns
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