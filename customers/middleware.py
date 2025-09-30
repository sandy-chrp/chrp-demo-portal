# customers/middleware.py - Fixed Version
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
import json

class CustomerSecurityMiddleware(MiddlewareMixin):
    """Enhanced security middleware for customer portal"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Skip security for admin and auth URLs
        if any(request.path.startswith(path) for path in ['/admin/', '/django-admin/', '/auth/', '/static/', '/media/']):
            return None
        
        # Only apply to authenticated customer users
        if not request.user.is_authenticated:
            return None
            
        # Check if user has is_approved attribute (customer users)
        if not hasattr(request.user, 'is_approved'):
            return None
        
        # Check if user is approved
        if not request.user.is_approved:
            if '/dashboard/' in request.path:
                return redirect('accounts:pending_approval')
        
        # Track user session (with error handling)
        try:
            self._track_session(request)
        except Exception as e:
            # Log error but don't break the request
            print(f"Session tracking error: {e}")
        
        # Check for suspicious activity
        if self._is_suspicious_activity(request):
            try:
                self._log_security_violation(request, 'suspicious_navigation')
            except Exception as e:
                print(f"Security logging error: {e}")
        
        return None
    
    def _track_session(self, request):
        """Track customer session for security monitoring"""
        if not request.user.is_authenticated:
            return
        
        session_key = request.session.session_key
        if not session_key:
            return
        
        ip_address = self._get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Import here to avoid circular imports
        from .models import CustomerSession
        
        # Update or create session record with proper error handling
        try:
            # Try to get existing session first
            session = CustomerSession.objects.filter(
                user=request.user,
                session_key=session_key
            ).first()
            
            if session:
                # Update existing session
                session.last_activity = timezone.now()
                session.save(update_fields=['last_activity'])
            else:
                # Create new session
                CustomerSession.objects.create(
                    user=request.user,
                    session_key=session_key,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
        except Exception as e:
            # Handle any database errors gracefully
            print(f"Session tracking error: {e}")
    
    def _is_suspicious_activity(self, request):
        """Check for suspicious activity patterns"""
        try:
            suspicious_patterns = [
                # Multiple rapid requests
                'bot' in request.META.get('HTTP_USER_AGENT', '').lower(),
                'crawler' in request.META.get('HTTP_USER_AGENT', '').lower(),
                'spider' in request.META.get('HTTP_USER_AGENT', '').lower(),
                
                # Suspicious headers
                request.META.get('HTTP_X_FORWARDED_FOR') and ',' in request.META.get('HTTP_X_FORWARDED_FOR', ''),
                
                # Direct file access attempts
                any(ext in request.path for ext in ['.mp4', '.avi', '.mov', '.jpg', '.png']),
            ]
            
            return any(suspicious_patterns)
        except Exception:
            return False
    
    def _log_security_violation(self, request, violation_type):
        """Log security violation"""
        if not request.user.is_authenticated:
            return
        
        try:
            from .models import SecurityViolation
            SecurityViolation.objects.create(
                user=request.user,
                violation_type=violation_type,
                description=f"Suspicious activity detected: {request.path}",
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                page_url=request.build_absolute_uri(),
                referrer=request.META.get('HTTP_REFERER', ''),
            )
        except Exception as e:
            print(f"Security violation logging error: {e}")
    
    def _get_client_ip(self, request):
        """Get real client IP address"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            return ip
        except Exception:
            return '127.0.0.1'

class ContentProtectionMiddleware(MiddlewareMixin):
    """Middleware to add security headers for content protection"""
    
    def process_response(self, request, response):
        # Apply only to customer portal pages
        if '/dashboard/' in request.path:
            # Prevent framing
            response['X-Frame-Options'] = 'DENY'
            
            # Prevent MIME type sniffing
            response['X-Content-Type-Options'] = 'nosniff'
            
            # XSS Protection
            response['X-XSS-Protection'] = '1; mode=block'
            
            # Content Security Policy for enhanced security
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "img-src 'self' data:; "
                "media-src 'self'; "
                "font-src 'self' https://cdnjs.cloudflare.com; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none';"
            )
            response['Content-Security-Policy'] = csp_policy
            
            # Prevent caching of sensitive content
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            # Referrer Policy
            response['Referrer-Policy'] = 'same-origin'
        
        return response