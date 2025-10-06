# core/webgl_views.py
import os
import zipfile
import json
import mimetypes
from pathlib import Path
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.text import slugify
from demos.models import Demo, DemoView
import tempfile
import shutil
from django.contrib import messages
from django.core.cache import cache
import hashlib

@staff_member_required
def admin_webgl_preview(request, demo_id):
    demo = get_object_or_404(Demo, id=demo_id, file_type='webgl')
    
    if not demo.webgl_file:
        messages.error(request, "No WebGL file attached to this demo")
        return redirect('core:admin_demo_detail', demo_id=demo_id)
    
    # Import at top of file
    from accounts.models import CustomUser
    from demos.models import DemoRequest
    
    context = {
        'demo': demo,
        'is_admin_preview': True,
        'pending_approvals': CustomUser.objects.filter(is_approved=False).count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
        'open_enquiries': 0,  # Adjust based on your Enquiry model
    }
    
    return render(request, 'admin/demos/webgl_preview.html', context)

@staff_member_required
def admin_universal_preview(request, demo_id):
    """Admin preview using Universal Viewer for both video and WebGL"""
    demo = get_object_or_404(Demo, id=demo_id)
    
    if demo.file_type == 'webgl' and not demo.webgl_file:
        messages.error(request, "WebGL file not found")
        return redirect('core:admin_demo_detail', demo_id=demo_id)
    elif demo.file_type == 'video' and not demo.video_file:
        messages.error(request, "Video file not found")
        return redirect('core:admin_demo_detail', demo_id=demo_id)
    
    # Add missing context for sidebar
    from accounts.models import CustomUser
    from demos.models import DemoRequest
    
    context = {
        'demo': demo,
        'is_admin_preview': True,
        'viewer_mode': 'universal',
        'pending_approvals': CustomUser.objects.filter(is_approved=False, is_active=True).count(),
        'demo_requests_pending': DemoRequest.objects.filter(status='pending').count(),
        'open_enquiries': 0,
    }
    
    return render(request, 'admin/demos/universal_preview.html', context)


@login_required
def universal_viewer(request, demo_id):
    """Universal viewer for customers - handles both video and WebGL"""
    demo = get_object_or_404(Demo, id=demo_id, is_active=True)
    
    # Check customer access
    if not demo.can_customer_access(request.user):
        return HttpResponse("You don't have access to this demo", status=403)
    
    # Track view
    DemoView.objects.update_or_create(
        demo=demo,
        user=request.user,
        defaults={'ip_address': request.META.get('REMOTE_ADDR')}
    )
    
    # Increment view count
    demo.views_count += 1
    demo.save(update_fields=['views_count'])
    
    context = {
        'demo': demo,
        'is_customer_view': True,
        'viewer_mode': 'universal',
    }
    
    return render(request, 'core/demos/universal_viewer.html', context)

@xframe_options_exempt
@login_required
def serve_webgl_content(request, demo_id):
    """
    Serve WebGL content - handles different file types:
    - HTML files: Serve directly with proper headers
    - ZIP files: Extract and serve index.html
    - GLTF/GLB files: Serve with model-viewer wrapper
    """
    try:
        demo = get_object_or_404(Demo, id=demo_id, file_type='webgl')
        
        # Check access permissions
        if not request.user.is_staff and not demo.can_customer_access(request.user):
            return HttpResponse("Access denied", status=403)
        
        if not demo.webgl_file:
            return HttpResponse(
                "<h1>Error</h1><p>No WebGL file attached to this demo.</p>",
                status=404,
                content_type='text/html'
            )
        
        # Handle cloud storage (S3, etc.) - redirect to signed URL
        try:
            file_path = demo.webgl_file.path
        except (NotImplementedError, AttributeError):
            # For cloud storage, serve via direct URL
            file_url = demo.webgl_file.url
            file_name = os.path.basename(demo.webgl_file.name)
            file_extension = os.path.splitext(file_name)[1].lower()
            
            # For HTML/ZIP, we need to fetch and process
            if file_extension in ['.html', '.zip']:
                import requests
                try:
                    response = requests.get(file_url, timeout=30)
                    response.raise_for_status()
                    
                    if file_extension == '.html':
                        content = response.text
                        content = inject_base_url(content)
                        http_response = HttpResponse(content, content_type='text/html')
                        http_response['X-Frame-Options'] = 'SAMEORIGIN'
                        return http_response
                    
                    elif file_extension == '.zip':
                        # Save temporarily and process
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                            tmp_file.write(response.content)
                            tmp_path = tmp_file.name
                        
                        result = serve_zip_content(demo, tmp_path)
                        os.unlink(tmp_path)  # Clean up
                        return result
                        
                except requests.RequestException as e:
                    return HttpResponse(
                        f"<h1>Error</h1><p>Unable to load WebGL file from storage: {str(e)}</p>",
                        status=500,
                        content_type='text/html'
                    )
            
            # For 3D models, generate viewer HTML
            elif file_extension in ['.gltf', '.glb']:
                return serve_3d_model(demo, request)
            
            else:
                return HttpResponse(
                    f"<h1>Unsupported File Type</h1><p>File type {file_extension} is not supported.</p>",
                    status=400,
                    content_type='text/html'
                )
        
        # Local file handling
        if not os.path.exists(file_path):
            return HttpResponse(
                "<h1>Error</h1><p>WebGL file not found on server.</p>",
                status=404,
                content_type='text/html'
            )
        
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Handle different file types
        if file_extension == '.html':
            return serve_html_file(file_path)
        
        elif file_extension == '.zip':
            return serve_zip_content(demo, file_path)
        
        elif file_extension in ['.gltf', '.glb']:
            return serve_3d_model(demo, request)
        
        else:
            return HttpResponse(
                f"<h1>Unsupported File Type</h1><p>File extension {file_extension} is not supported. "
                f"Supported types: .html, .zip, .gltf, .glb</p>",
                status=400,
                content_type='text/html'
            )
            
    except Demo.DoesNotExist:
        return HttpResponse(
            "<h1>Error</h1><p>Demo not found.</p>",
            status=404,
            content_type='text/html'
        )
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc() if settings.DEBUG else ""
        
        return HttpResponse(
            f"""
            <html>
            <head>
                <title>Error Loading WebGL</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
                    .error-container {{ 
                        background: white; 
                        padding: 30px; 
                        border-radius: 8px; 
                        max-width: 600px; 
                        margin: 0 auto;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}
                    h1 {{ color: #e74c3c; }}
                    .error-message {{ color: #555; margin: 20px 0; }}
                    .error-details {{ 
                        background: #f8f9fa; 
                        padding: 15px; 
                        border-radius: 4px; 
                        overflow: auto;
                        font-size: 12px;
                        font-family: monospace;
                    }}
                    .btn {{ 
                        display: inline-block;
                        padding: 10px 20px;
                        background: #3498db;
                        color: white;
                        text-decoration: none;
                        border-radius: 4px;
                        margin-top: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="error-container">
                    <h1>⚠️ Error Loading WebGL Content</h1>
                    <div class="error-message">
                        <p>An unexpected error occurred while loading the WebGL content:</p>
                        <p><strong>{str(e)}</strong></p>
                    </div>
                    {'<div class="error-details"><pre>' + error_details + '</pre></div>' if error_details else ''}
                    <a href="javascript:history.back()" class="btn">← Go Back</a>
                </div>
            </body>
            </html>
            """,
            status=500,
            content_type='text/html'
        )
def serve_html_file(file_path):
    """Serve HTML file directly with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Inject base URL for relative paths
        content = inject_base_url(content)
        
        response = HttpResponse(content, content_type='text/html')
        response['X-Frame-Options'] = 'SAMEORIGIN'
        response['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response
        
    except UnicodeDecodeError:
        # Try different encoding
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            content = inject_base_url(content)
            response = HttpResponse(content, content_type='text/html')
            response['X-Frame-Options'] = 'SAMEORIGIN'
            return response
        except Exception as e:
            return HttpResponse(
                f"<h1>Error</h1><p>Unable to read HTML file: {str(e)}</p>",
                status=500,
                content_type='text/html'
            )
    
    except Exception as e:
        return HttpResponse(
            f"<h1>Error</h1><p>Error loading HTML file: {str(e)}</p>",
            status=500,
            content_type='text/html'
        )


def serve_zip_content(demo, zip_path):
    """Extract and serve content from ZIP file"""
    temp_dir = None
    
    try:
        temp_dir = tempfile.mkdtemp(prefix='webgl_')
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.startswith('/') or '..' in member:
                    continue
            zip_ref.extractall(temp_dir)
        
        # Find HTML files
        html_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith('.html'):
                    html_files.append(os.path.join(root, file))
        
        index_path = None
        for html_file in html_files:
            if 'index.html' in html_file.lower():
                index_path = html_file
                break
        
        if not index_path and html_files:
            index_path = html_files[0]
        
        if not index_path:
            return HttpResponse(
                "<h1>Error</h1><p>No HTML file found in ZIP archive.</p>",
                status=400,
                content_type='text/html'
            )
        
        with open(index_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix React %PUBLIC_URL% placeholder
        import re
        content = content.replace('%PUBLIC_URL%', '')
        
        # Remove manifest.json reference if it doesn't exist
        content = re.sub(r'<link[^>]*rel="manifest"[^>]*>', '', content)
        
        # Don't add base tag - it causes issues with ZIP content
        # Instead, the ZIP should be self-contained
        
        response = HttpResponse(content, content_type='text/html')
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response
        
    except Exception as e:
        return HttpResponse(
            f"<h1>Error</h1><p>Error processing ZIP: {str(e)}</p>",
            status=500,
            content_type='text/html'
        )
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

def serve_3d_model(demo, request):
    """Serve GLTF/GLB files using model-viewer"""
    model_url = demo.webgl_file.url
    
    # Create HTML wrapper with model-viewer
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{demo.title} - 3D Model</title>
        <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                height: 100vh;
                display: flex;
                flex-direction: column;
            }}
            .header {{
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                padding: 1rem;
                color: white;
                text-align: center;
            }}
            .header h1 {{
                font-size: 1.5rem;
                margin-bottom: 0.25rem;
            }}
            .header p {{
                font-size: 0.9rem;
                opacity: 0.9;
            }}
            .viewer-container {{
                flex: 1;
                padding: 1rem;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            model-viewer {{
                width: 100%;
                height: 100%;
                max-width: 1200px;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            }}
            .controls {{
                position: absolute;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0, 0, 0, 0.7);
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                font-size: 0.85rem;
                backdrop-filter: blur(10px);
            }}
            .loading {{
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: 1.2rem;
                color: #667eea;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{demo.title}</h1>
            <p>{demo.description}</p>
        </div>
        
        <div class="viewer-container">
            <model-viewer
                src="{model_url}"
                alt="{demo.title}"
                auto-rotate
                camera-controls
                shadow-intensity="1"
                exposure="1"
                tone-mapping="neutral"
                skybox-image="https://cdn.jsdelivr.net/gh/mrdoob/three.js@master/examples/textures/2294472375_24a3b8ef46_o.jpg"
                environment-image="https://cdn.jsdelivr.net/gh/mrdoob/three.js@master/examples/textures/2294472375_24a3b8ef46_o.jpg"
                poster="{demo.thumbnail.url if demo.thumbnail else ''}"
                loading="eager"
                reveal="auto"
                interaction-prompt="auto"
                ar
                ar-modes="webxr scene-viewer quick-look"
                magic-leap
                ios-src="{model_url}">
                
                <div class="loading" slot="pending">Loading 3D Model...</div>
                
                <button slot="ar-button" style="background: white; border-radius: 4px; border: none; position: absolute; top: 16px; right: 16px; padding: 0.5rem 1rem; font-weight: 600;">
                    View in AR
                </button>
            </model-viewer>
        </div>
        
        <div class="controls">
            <span>🖱️ Drag to rotate • 📱 Pinch to zoom • 🎯 Double-tap to reset</span>
        </div>
        
        <script>
            // Handle model loading events
            const modelViewer = document.querySelector('model-viewer');
            
            modelViewer.addEventListener('load', () => {{
                console.log('Model loaded successfully');
            }});
            
            modelViewer.addEventListener('error', (event) => {{
                console.error('Error loading model:', event);
                alert('Error loading 3D model. Please try again later.');
            }});
            
            // Add keyboard controls
            document.addEventListener('keydown', (e) => {{
                const mv = document.querySelector('model-viewer');
                if (e.key === 'r' || e.key === 'R') {{
                    mv.resetTurntableRotation();
                    mv.cameraOrbit = mv.cameraOrbit;
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    response = HttpResponse(html_content, content_type='text/html')
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response

def inject_base_url(html_content):
    """Inject base URL for relative asset paths"""
    base_tag = f'<base href="{settings.MEDIA_URL}">'
    
    # Add base tag if not present
    if '<base' not in html_content.lower():
        if '<head>' in html_content.lower():
            html_content = html_content.replace('<head>', f'<head>\n{base_tag}', 1)
        elif '<html>' in html_content.lower():
            html_content = html_content.replace('<html>', f'<html>\n<head>{base_tag}</head>', 1)
        else:
            html_content = f'<head>{base_tag}</head>\n{html_content}'
    
    return html_content

def inject_zip_asset_handler(html_content, demo_id, temp_dir):
    """Inject JavaScript to handle asset loading from extracted ZIP"""
    
    # Store extracted files info
    assets_map = {}
    for root, dirs, files in os.walk(temp_dir):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, temp_dir)
            assets_map[relative_path.replace('\\', '/')] = file_path
    
    # Create asset handler script
    asset_script = f"""
    <script>
        window.webglAssets = {json.dumps(assets_map)};
        window.webglDemoId = {demo_id};
        
        // Override fetch for local assets
        const originalFetch = window.fetch;
        window.fetch = function(url, options) {{
            // Check if URL is relative and exists in assets
            const urlStr = url.toString();
            if (!urlStr.startsWith('http')) {{
                const assetPath = urlStr.replace(/^\\.?\\//, '');
                if (window.webglAssets[assetPath]) {{
                    // Fetch from server endpoint
                    return originalFetch('/api/webgl-asset/' + window.webglDemoId + '/' + assetPath, options);
                }}
            }}
            return originalFetch(url, options);
        }};
    </script>
    """
    
    # Inject script into head
    if '<head>' in html_content:
        html_content = html_content.replace('<head>', f'<head>\n{asset_script}')
    else:
        html_content = f'{asset_script}\n{html_content}'
    
    return html_content


@csrf_exempt
@login_required
def serve_webgl_asset(request, demo_id, asset_path):
    """Serve individual assets from WebGL ZIP files"""
    demo = get_object_or_404(Demo, id=demo_id, file_type='webgl')
    
    # Check permissions
    if not request.user.is_staff and not demo.can_customer_access(request.user):
        return HttpResponse("Access denied", status=403)
    
    if not demo.webgl_file or not demo.webgl_file.path.endswith('.zip'):
        raise Http404("Asset not found")
    
    try:
        # Extract requested file from ZIP
        with zipfile.ZipFile(demo.webgl_file.path, 'r') as zip_ref:
            # Sanitize path
            asset_path = asset_path.replace('..', '').strip('/')
            
            # Check if file exists in ZIP
            if asset_path not in zip_ref.namelist():
                raise Http404(f"Asset not found: {asset_path}")
            
            # Read file content
            file_content = zip_ref.read(asset_path)
            
            # Determine content type
            content_type, _ = mimetypes.guess_type(asset_path)
            if not content_type:
                if asset_path.endswith('.glsl'):
                    content_type = 'text/plain'
                elif asset_path.endswith('.json'):
                    content_type = 'application/json'
                else:
                    content_type = 'application/octet-stream'
            
            response = HttpResponse(file_content, content_type=content_type)
            
            # Add CORS headers for WebGL assets
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            
            return response
            
    except Exception as e:
        return HttpResponse(f"Error loading asset: {str(e)}", status=500)


@staff_member_required
def webgl_file_info(request, demo_id):
    """Get information about WebGL file structure (for debugging)"""
    demo = get_object_or_404(Demo, id=demo_id, file_type='webgl')
    
    if not demo.webgl_file:
        return JsonResponse({'error': 'No WebGL file found'}, status=404)
    
    file_info = {
        'filename': os.path.basename(demo.webgl_file.name),
        'size': demo.webgl_file.size,
        'extension': os.path.splitext(demo.webgl_file.name)[1].lower(),
    }
    
    # If ZIP file, list contents
    if file_info['extension'] == '.zip':
        try:
            with zipfile.ZipFile(demo.webgl_file.path, 'r') as zip_ref:
                file_info['contents'] = []
                for file_name in zip_ref.namelist():
                    info = zip_ref.getinfo(file_name)
                    file_info['contents'].append({
                        'name': file_name,
                        'size': info.file_size,
                        'compressed_size': info.compress_size,
                    })
        except Exception as e:
            file_info['error'] = str(e)
    
    return JsonResponse(file_info)