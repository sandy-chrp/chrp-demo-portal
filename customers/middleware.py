# customers/middleware.py - COMPLETE CORRECTED VERSION

from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.conf import settings
from django.utils import timezone
import os
import mimetypes
import json



class CustomerSecurityMiddleware:
    """Middleware to check customer approval status"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Paths that should be exempt from customer checks
        self.exempt_paths = [
            '/landing/',
            '/contact/',
            '/contact-sales/',
            '/accounts/',
            '/admin/',
            '/static/',
            '/media/',
            '/__debug__/',
            '/customer/ajax/',  # ✅ ADD THIS
        ]
    
    def __call__(self, request):
        # ✅ CRITICAL: Skip AJAX requests completely
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.get_response(request)
        
        # Check if path is exempt
        if any(request.path.startswith(path) for path in self.exempt_paths):
            return self.get_response(request)
        
        # ✅ CRITICAL: Skip for staff users
        if request.user.is_authenticated and request.user.is_staff:
            return self.get_response(request)
        
        # Check if user is in customer portal
        if request.path.startswith('/customer/'):
            # ✅ CRITICAL: Check authentication first
            if not request.user.is_authenticated:
                from django.shortcuts import redirect
                from django.urls import reverse
                login_url = reverse('accounts:signin')
                return redirect(f'{login_url}?next={request.path}')
            
            # ✅ CRITICAL: Check approval (but allow if staff)
            if not request.user.is_approved and not request.user.is_staff:
                from django.shortcuts import redirect
                from django.urls import reverse
                # Check if pending approval page exists
                try:
                    return redirect('accounts:pending_approval')
                except:
                    # If pending approval page doesn't exist, just continue
                    pass
        
        return self.get_response(request)


class ContentProtectionMiddleware(MiddlewareMixin):
    """Middleware to add security headers for content protection"""
    
    def process_response(self, request, response):
        # Apply only to customer portal pages (not WebGL content)
        if '/customer/' in request.path and '/webgl-content/' not in request.path:
            # Prevent framing
            response['X-Frame-Options'] = 'SAMEORIGIN'  # Changed from DENY to allow iframes
            
            # Prevent MIME type sniffing
            response['X-Content-Type-Options'] = 'nosniff'
            
            # XSS Protection
            response['X-XSS-Protection'] = '1; mode=block'
            
            # Content Security Policy for enhanced security
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://ajax.googleapis.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https:; "
                "media-src 'self' blob:; "
                "font-src 'self' https://cdnjs.cloudflare.com data:; "
                "connect-src 'self'; "
                "frame-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
            )
            response['Content-Security-Policy'] = csp_policy
            
            # Prevent caching of sensitive content
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            # Referrer Policy
            response['Referrer-Policy'] = 'same-origin'
        
        return response


class WebGLFileMiddleware:
    """Middleware to serve WebGL files without template processing"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if this is a WebGL file request
        if '/webgl-content/' in request.path:
            try:
                response = self.serve_webgl_file(request)
                if response:
                    return response
            except Http404:
                raise
            except Exception as e:
                print(f"WebGL middleware error: {e}")
        
        return self.get_response(request)
    
    def serve_webgl_file(self, request):
        """Serve WebGL files directly without Django template processing"""
        
        # Extract slug and filepath from URL
        # Expected format: /customer/demos/{slug}/webgl-content/{filepath}
        path_parts = request.path.split('/webgl-content/')
        if len(path_parts) != 2:
            raise Http404("Invalid WebGL content path")
        
        filepath = path_parts[1]
        
        # Extract demo slug from the path
        demo_slug = None
        if '/demos/' in path_parts[0]:
            slug_parts = path_parts[0].split('/demos/')
            if len(slug_parts) == 2:
                demo_slug = slug_parts[1].rstrip('/')
        
        if not demo_slug:
            raise Http404("Demo not found")
        
        # Get the demo to find extracted path
        try:
            from demos.models import Demo
            demo = Demo.objects.filter(slug=demo_slug, is_active=True, file_type='webgl').first()
            
            if not demo:
                raise Http404("Demo not found")
            
            # Check user access (if user is authenticated)
            if request.user.is_authenticated:
                if not demo.can_customer_access(request.user):
                    raise Http404("Access denied")
            
            # Build full file path
            if demo.extracted_path:
                full_path = os.path.join(settings.MEDIA_ROOT, demo.extracted_path, filepath)
            else:
                # For standalone HTML files
                full_path = demo.webgl_file.path if demo.webgl_file else None
            
        except Exception as e:
            print(f"Demo lookup error: {e}")
            raise Http404("Demo not found")
        
        # Verify file exists and is not a directory
        if not full_path or not os.path.isfile(full_path):
            raise Http404(f"File not found: {filepath}")
        
        # Security check: ensure file is within allowed directory
        real_path = os.path.realpath(full_path)
        base_path = os.path.realpath(settings.MEDIA_ROOT)
        if not real_path.startswith(base_path):
            raise Http404("Invalid file path")
        
        # Determine content type
        content_type, _ = mimetypes.guess_type(full_path)
        
        # Set proper content types for WebGL files
        if filepath.endswith('.js'):
            content_type = 'application/javascript; charset=utf-8'
        elif filepath.endswith('.wasm'):
            content_type = 'application/wasm'
        elif filepath.endswith('.data'):
            content_type = 'application/octet-stream'
        elif filepath.endswith('.html'):
            content_type = 'text/html; charset=utf-8'
        elif filepath.endswith('.json'):
            content_type = 'application/json; charset=utf-8'
        elif not content_type:
            content_type = 'application/octet-stream'
        
        # Read and return file
        try:
            with open(full_path, 'rb') as f:
                file_data = f.read()
            
            response = HttpResponse(file_data, content_type=content_type)
            
            # Add CORS headers for WebGL
            response['Access-Control-Allow-Origin'] = '*'
            response['X-Content-Type-Options'] = 'nosniff'
            
            # Cache control for better performance
            response['Cache-Control'] = 'public, max-age=3600'
            
            # Important: Don't add X-Frame-Options DENY for WebGL content
            # as it needs to be displayed in iframe
            
            return response
            
        except Exception as e:
            print(f"❌ Error reading file {filepath}: {e}")
            raise Http404("Error serving file")
        

class WebGLCompressionMiddleware:
    """Middleware to compress WebGL responses on-the-fly"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Only compress WebGL content
        if '/webgl-content/' in request.path:
            # Check if client accepts gzip
            if 'gzip' in request.META.get('HTTP_ACCEPT_ENCODING', ''):
                # Check if already compressed
                if 'Content-Encoding' not in response:
                    # Check if content is compressible
                    content_type = response.get('Content-Type', '')
                    if any(ct in content_type for ct in ['javascript', 'json', 'text', 'css']):
                        # Compress on-the-fly
                        if hasattr(response, 'content') and len(response.content) > 1024:
                            try:
                                import gzip
                                compressed = gzip.compress(response.content, compresslevel=6)
                                response.content = compressed
                                response['Content-Encoding'] = 'gzip'
                                response['Content-Length'] = len(compressed)
                            except:
                                pass
        
        return response        