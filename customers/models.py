# customers/models.py - Complete Version
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.http import HttpResponse, Http404
from django.conf import settings
import os
import mimetypes
User = get_user_model()

class CustomerSession(models.Model):
    """Track customer session for security"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_sessions')
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # Security tracking
    suspicious_activity = models.BooleanField(default=False)
    security_violations = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'customer_sessions'
        ordering = ['-login_time']
        unique_together = ['user', 'session_key']
    
    def __str__(self):
        return f"{self.user.email} - {self.ip_address}"

class CustomerActivity(models.Model):
    """Track customer activities for security monitoring"""
    
    ACTIVITY_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('demo_view', 'Demo View'),
        ('demo_like', 'Demo Like'),
        ('demo_request', 'Demo Request'),
        ('demo_request_cancelled', 'Demo Request Cancelled'),
        ('enquiry_sent', 'Enquiry Sent'),
        ('security_violation', 'Security Violation'),
        ('suspicious_activity', 'Suspicious Activity'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Additional data (JSON field for flexibility)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'customer_activities'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_activity_type_display()}"

class SecurityViolation(models.Model):
    """Track security violations for monitoring"""
    
    VIOLATION_TYPES = [
        ('screenshot_attempt', 'Screenshot Attempt'),
        ('devtools_detected', 'Developer Tools Detected'),
        ('context_menu', 'Right Click Menu'),
        ('copy_attempt', 'Copy Attempt'),
        ('print_attempt', 'Print Attempt'),
        ('drag_attempt', 'Drag & Drop Attempt'),
        ('screen_recording', 'Screen Recording Attempt'),
        ('suspicious_navigation', 'Suspicious Navigation'),
        ('multiple_sessions', 'Multiple Active Sessions'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='security_violations')
    violation_type = models.CharField(max_length=30, choices=VIOLATION_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    
    # Context information
    page_url = models.URLField(blank=True)
    referrer = models.URLField(blank=True)
    
    # Response taken
    action_taken = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_violations'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.get_violation_type_display()}"
    

class WebGLFileMiddleware:
    """Middleware to serve WebGL files without template processing"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if this is a WebGL file request
        if '/webgl-content/' in request.path:
            try:
                return self.serve_webgl_file(request)
            except:
                pass
        
        return self.get_response(request)
    
    def serve_webgl_file(self, request):
        # Extract path components
        path_parts = request.path.split('/webgl-content/')
        if len(path_parts) != 2:
            raise Http404()
        
        filepath = path_parts[1]
        
        # Build full path (you need to determine this based on your structure)
        # This is a simplified version
        base_path = os.path.join(settings.MEDIA_ROOT, 'webgl_extracted')
        full_path = os.path.join(base_path, filepath)
        
        if not os.path.isfile(full_path):
            raise Http404()
        
        # Get content type
        content_type, _ = mimetypes.guess_type(full_path)
        if not content_type:
            content_type = 'application/octet-stream'
        
        # Read and return file
        with open(full_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response['Access-Control-Allow-Origin'] = '*'
            return response
