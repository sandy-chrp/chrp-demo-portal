from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404, HttpResponse, FileResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, F

from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
from django.urls import reverse

# ✅ CRITICAL: Import these for date/time handling
from datetime import datetime, timedelta, time as datetime_time
from django.utils.timesince import timesince

import json
import mimetypes
import os

# Your app imports
from accounts.models import CustomUser, BusinessCategory, BusinessSubCategory
from demos.models import (
    Demo, DemoCategory, DemoRequest, DemoView, 
    DemoLike, DemoFeedback, TimeSlot
)
from enquiries.models import BusinessEnquiry, EnquiryCategory, EnquiryResponse
from notifications.models import Notification
from core.models import SiteSettings, ContactMessage
from customers.models import CustomerActivity
import pytz
from .models import SecurityViolation
from .utils import log_customer_activity, get_client_ip
from django.views.decorators.http import require_POST
from .utils import log_customer_activity, get_client_ip, log_security_violation

def get_customer_context(user):
    """Get common context data for customer views"""
    context = {
        # Demo stats
        'total_demos_watched': DemoView.objects.filter(user=user).count(),
        'total_demo_requests': DemoRequest.objects.filter(user=user).count(),
        'pending_demo_requests': DemoRequest.objects.filter(
            user=user, 
            status='pending'
        ).count(),
        
        # Enquiry stats
        'total_enquiries': BusinessEnquiry.objects.filter(user=user).count(),
        'open_enquiries': BusinessEnquiry.objects.filter(
            user=user, 
            status__in=['open', 'in_progress']
        ).count(),
        
        # Notification stats
        'unread_notifications': Notification.objects.filter(
            user=user, 
            is_read=False
        ).count(),
        
        # Recent activity
        'recent_demos': Demo.objects.filter(
            is_active=True,
            target_customers=user
        )[:3] if not Demo.objects.filter(target_customers=user).exists() 
            else Demo.objects.filter(is_active=True)[:3],
        
        'recent_notifications': Notification.objects.filter(
            user=user
        ).order_by('-created_at')[:3],
    }
    return context

from django.db.models import Count, Q

@login_required
def customer_dashboard(request):
    """Customer main dashboard - WITH WEBGL SUPPORT"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    context = get_customer_context(request.user)
    
    # Get user's business category and subcategory
    user_business_category = request.user.business_category
    user_business_subcategory = request.user.business_subcategory
    
    # Get featured demos with business category filtering
    featured_demos_query = Demo.objects.filter(
        is_active=True,
        is_featured=True
    ).prefetch_related(
        'target_business_categories',
        'target_business_subcategories',
        'target_customers'
    )
    
    # Filter by business categories
    featured_demos = []
    for demo in featured_demos_query:
        # Check business category access
        if demo.is_available_for_business(user_business_category, user_business_subcategory):
            # Check customer access
            if demo.can_customer_access(request.user):
                featured_demos.append(demo)
    
    # Limit to 12 demos
    featured_demos = featured_demos[:12]
    
    context.update({
        'recent_demo_requests': DemoRequest.objects.filter(
            user=request.user
        ).select_related('demo').order_by('-created_at')[:3],
        
        'recent_enquiries': BusinessEnquiry.objects.filter(
            user=request.user
        ).order_by('-created_at')[:3],
        
        'featured_demos': featured_demos,
        
        'stats': {
            'demos_watched': context['total_demos_watched'],
            'demo_requests': context['total_demo_requests'],
            'enquiries_sent': context['total_enquiries'],
            'notifications': context['unread_notifications'],
        }
    })
    
    return render(request, 'customers/dashboard.html', context)



@login_required
def browse_demos(request):
    """Browse available demo videos with customer access control - WITH WEBGL SUPPORT"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    # Get user's business category and subcategory
    user_business_category = request.user.business_category
    user_business_subcategory = request.user.business_subcategory
    
    # Get filter parameters
    business_category_id = request.GET.get('business_category')
    business_subcategory_id = request.GET.get('business_subcategory')
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'newest')
    
    # Base queryset - get all active demos
    demos_query = Demo.objects.filter(is_active=True).prefetch_related(
        'target_business_categories',
        'target_business_subcategories',
        'target_customers'
    )
    
    # Filter demos based on business category access and customer access
    accessible_demos = []
    for demo in demos_query:
        # Check business category access
        if demo.is_available_for_business(user_business_category, user_business_subcategory):
            # Check customer access
            if demo.can_customer_access(request.user):
                accessible_demos.append(demo.id)
    
    # Filter by accessible demo IDs
    demos = Demo.objects.filter(id__in=accessible_demos)
    
    # Apply additional filters
    if business_category_id:
        demos = demos.filter(
            Q(target_business_categories__id=business_category_id) |
            Q(target_business_categories__isnull=True)
        ).distinct()
    
    if business_subcategory_id:
        demos = demos.filter(
            Q(target_business_subcategories__id=business_subcategory_id) |
            Q(target_business_subcategories__isnull=True)
        ).distinct()
    
    # Apply search filter
    if search_query:
        demos = demos.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'newest':
        demos = demos.order_by('-created_at')
    elif sort_by == 'oldest':
        demos = demos.order_by('created_at')
    elif sort_by == 'popular':
        demos = demos.order_by('-views_count')
    elif sort_by == 'liked':
        demos = demos.order_by('-likes_count')
    elif sort_by == 'title':
        demos = demos.order_by('title')
    else:
        demos = demos.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(demos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get ALL business categories for filter dropdown
    business_categories = BusinessCategory.objects.filter(
        is_active=True
    ).order_by('sort_order', 'name')
    
    # Get ALL subcategories for dynamic JavaScript filtering
    business_subcategories = BusinessSubCategory.objects.filter(
        is_active=True
    ).select_related('category').order_by('category__sort_order', 'sort_order', 'name')
    
    # Add user interaction data
    user_views = DemoView.objects.filter(user=request.user).values_list('demo_id', flat=True)
    user_likes = DemoLike.objects.filter(user=request.user).values_list('demo_id', flat=True)
    
    context = get_customer_context(request.user)
    context.update({
        'page_obj': page_obj,
        'business_categories': business_categories,
        'business_subcategories': business_subcategories,
        'current_business_category': int(business_category_id) if business_category_id else None,
        'current_business_subcategory': int(business_subcategory_id) if business_subcategory_id else None,
        'search_query': search_query,
        'sort_by': sort_by,
        'user_views': list(user_views),
        'user_likes': list(user_likes),
    })
    
    return render(request, 'customers/browse_demos.html', context)

@login_required
def demo_detail(request, slug):
    """
    Demo detail/hub page - handles both video and WebGL
    Redirects WebGL to viewer, shows video player for videos
    """
    demo = get_object_or_404(Demo, slug=slug, is_active=True)
    
    # Check if user can access this demo
    if not demo.can_customer_access(request.user):
        messages.error(request, "You don't have permission to access this demo.")
        return redirect('customers:browse_demos')
    
    # ✅ NEW: Auto-redirect WebGL demos to 3D viewer
    if demo.file_type == 'webgl':
        # Record view
        DemoView.objects.update_or_create(
            demo=demo,
            user=request.user,
            defaults={'ip_address': get_client_ip(request)}
        )
        # Increment view count using F()
        demo.views_count = F('views_count') + 1
        demo.save(update_fields=['views_count'])
        
        # Redirect to WebGL viewer
        return redirect('customers:webgl_viewer', slug=slug)
    
    # ✅ For video demos, continue with normal detail page
    # Record demo view
    DemoView.objects.update_or_create(
        demo=demo,
        user=request.user,
        defaults={'ip_address': get_client_ip(request)}
    )
    
    # Increment view count using F()
    demo.views_count = F('views_count') + 1
    demo.save(update_fields=['views_count'])
    
    # Check if user has liked this demo
    user_liked = DemoLike.objects.filter(demo=demo, user=request.user).exists()
    
    # Get related demos
    related_demos = Demo.objects.filter(
        is_active=True,
        file_type='video'  # Only show video demos in related
    ).exclude(id=demo.id)
    
    # Filter by business category if user has one
    if request.user.business_category:
        related_demos = related_demos.filter(
            target_business_categories=request.user.business_category
        )
    
    related_demos = related_demos[:3]
    
    context = {
        'demo': demo,
        'user_liked': user_liked,
        'related_demos': related_demos,
        'user_email': request.user.email,
    }
    
    return render(request, 'customers/demo_detail.html', context)

@login_required
@require_http_methods(["POST"])
def toggle_demo_like(request, demo_id):
    """AJAX endpoint to like/unlike demo"""
    if not request.user.is_approved:
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    demo = get_object_or_404(Demo, id=demo_id, is_active=True)
    
    # Check access
    if not demo.can_customer_access(request.user):
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    like_obj, created = DemoLike.objects.get_or_create(
        demo=demo,
        user=request.user
    )
    
    if not created:
        like_obj.delete()
        liked = False
        # Decrement likes count
        Demo.objects.filter(id=demo.id).update(likes_count=F('likes_count') - 1)
    else:
        liked = True
        # Increment likes count
        Demo.objects.filter(id=demo.id).update(likes_count=F('likes_count') + 1)
    
    # Get updated count
    demo.refresh_from_db()
    
    return JsonResponse({
        'liked': liked,
        'likes_count': demo.likes_count
    })

# customers/views.py - Fixed demo_requests view with status filtering
@login_required
def demo_requests(request):
    """Customer's demo requests list with status filtering"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '').strip()
    
    # Base queryset
    requests = DemoRequest.objects.filter(
        user=request.user
    ).select_related('demo', 'requested_time_slot', 'confirmed_time_slot')
    
    # Apply status filter
    if status_filter and status_filter in dict(DemoRequest.STATUS_CHOICES):
        requests = requests.filter(status=status_filter)
    
    # Order by newest first
    requests = requests.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get context
    context = get_customer_context(request.user)
    
    # Status counts
    status_counts = {}
    all_requests = DemoRequest.objects.filter(user=request.user)
    
    for status_key, status_label in DemoRequest.STATUS_CHOICES:
        status_counts[status_key] = all_requests.filter(status=status_key).count()
    
    status_counts['all'] = all_requests.count()
    
    context.update({
        'page_obj': page_obj,
        'status_choices': DemoRequest.STATUS_CHOICES,
        'current_status': status_filter,
        'status_counts': status_counts,
        'total_requests': status_counts['all'],
    })
    
    return render(request, 'customers/demo_requests.html', context)
from django.db.models import Count

@login_required
def webgl_viewer(request, slug):
    """
    WebGL 3D Viewer - Full screen viewer for WebGL demos
    """
    demo = get_object_or_404(Demo, slug=slug, is_active=True, file_type='webgl')
    
    # Check access permissions
    if not demo.can_customer_access(request.user):
        messages.error(request, "You don't have permission to access this demo.")
        return redirect('customers:browse_demos')
    
    # Check business category access
    if not demo.is_available_for_business(
        request.user.business_category,
        request.user.business_subcategory
    ):
        messages.error(request, "This demo is not available for your business category.")
        return redirect('customers:browse_demos')
    
    # Get WebGL content URL
    content_url = demo.get_webgl_index_url()
    
    if not content_url:
        messages.error(request, "WebGL content not available for this demo.")
        return redirect('customers:browse_demos')
    
    # Check if user has liked this demo
    user_liked = DemoLike.objects.filter(demo=demo, user=request.user).exists()
    
    # Determine viewer type
    viewer_type = demo.get_webgl_viewer_type()
    
    context = {
        'demo': demo,
        'content_url': content_url,
        'viewer_type': viewer_type,
        'user_liked': user_liked,
        'user_email': request.user.email,
    }
    
    return render(request, 'customers/webgl_viewer.html', context)

@login_required
def serve_webgl_file(request, slug, filepath):
    """Serve WebGL files with caching"""
    
    demo = get_object_or_404(Demo, slug=slug, is_active=True, file_type='webgl')
    
    # Normalize filepath
    filepath_normalized = filepath.replace('/', os.sep)
    
    # Build full file path
    if demo.extracted_path:
        full_path = os.path.join(settings.MEDIA_ROOT, demo.extracted_path, filepath_normalized)
    else:
        full_path = demo.webgl_file.path if demo.webgl_file else None
    
    # Verify file exists
    if not full_path or not os.path.isfile(full_path):
        raise Http404(f"File not found: {filepath}")
    
    # Security check
    real_path = os.path.realpath(full_path)
    base_path = os.path.realpath(settings.MEDIA_ROOT)
    if not real_path.startswith(base_path):
        raise Http404("Invalid file path")
    
    # Determine content type
    if filepath.endswith('.js'):
        content_type = 'application/javascript; charset=utf-8'
    elif filepath.endswith('.wasm'):
        content_type = 'application/wasm'
    elif filepath.endswith('.data'):
        content_type = 'application/octet-stream'
    elif filepath.endswith(('.html', '.htm')):
        content_type = 'text/html; charset=utf-8'
    elif filepath.endswith('.json'):
        content_type = 'application/json; charset=utf-8'
    elif filepath.endswith('.css'):
        content_type = 'text/css; charset=utf-8'
    elif filepath.endswith(('.jpg', '.jpeg')):
        content_type = 'image/jpeg'
    elif filepath.endswith('.png'):
        content_type = 'image/png'
    elif filepath.endswith('.ico'):
        content_type = 'image/x-icon'
    elif filepath.endswith('.mp4'):
        content_type = 'video/mp4'
    else:
        content_type, _ = mimetypes.guess_type(full_path)
        if not content_type:
            content_type = 'application/octet-stream'
    
    # Read file
    try:
        with open(full_path, 'rb') as f:
            file_content = f.read()
        
        # ✅ NEW: Inject base tag for HTML files
        if filepath.endswith(('.html', '.htm')):
            try:
                html_content = file_content.decode('utf-8')
                html_dir = os.path.dirname(filepath).replace('\\', '/')
                if html_dir:
                    base_url = f"/customer/demos/{slug}/webgl-content/{html_dir}/"
                else:
                    base_url = f"/customer/demos/{slug}/webgl-content/"
                
                base_tag = f'<base href="{base_url}">'
                
                if '<head>' in html_content:
                    html_content = html_content.replace('<head>', f'<head>\n    {base_tag}', 1)
                elif '<HEAD>' in html_content:
                    html_content = html_content.replace('<HEAD>', f'<HEAD>\n    {base_tag}', 1)
                
                file_content = html_content.encode('utf-8')
            except:
                pass
        
        response = HttpResponse(file_content, content_type=content_type)
        
        # ✅ NEW: Strong caching headers
        response['Cache-Control'] = 'public, max-age=31536000, immutable'  # 1 year
        response['Access-Control-Allow-Origin'] = '*'
        response['X-Content-Type-Options'] = 'nosniff'
        
        return response
        
    except Exception as e:
        print(f"❌ Error serving file: {e}")
        raise Http404("Error serving file")


@login_required
def request_demo(request):
    """Request demo - Enhanced with END TIME validation"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    demo_id = request.GET.get('demo')
    
    # ===== SPECIFIC DEMO REQUEST (from browse page) =====
    if demo_id:
        try:
            # Check customer access control
            selected_demo = Demo.objects.filter(
                id=demo_id,
                is_active=True
            ).annotate(
                customer_count=Count('target_customers')
            ).filter(
                Q(customer_count=0) |
                Q(target_customers=request.user)
            ).distinct().first()
            
            if not selected_demo:
                messages.error(request, 'This demo is not available to you. Please contact support for access.')
                return redirect('customers:browse_demos')
            
            # ===== POST - Handle specific demo booking =====
            if request.method == 'POST':
                requested_date_str = request.POST.get('requested_date')
                time_slot_id = request.POST.get('time_slot_id')
                notes = request.POST.get('notes', '').strip()
                
                try:
                    import pytz
                    
                    # Parse requested date
                    requested_date = datetime.strptime(requested_date_str, '%Y-%m-%d').date()
                    time_slot = TimeSlot.objects.get(id=time_slot_id, is_active=True)
                    
                    # Get current date and time in Indian timezone
                    indian_tz = pytz.timezone('Asia/Kolkata')
                    now_utc = timezone.now()
                    now_indian = now_utc.astimezone(indian_tz)
                    
                    today = now_indian.date()
                    current_time = now_indian.time()
                    
                    print(f"\n{'='*60}")
                    print(f"🔍 BOOKING VALIDATION - SPECIFIC DEMO")
                    print(f"{'='*60}")
                    print(f"📅 Requested Date: {requested_date}")
                    print(f"⏰ Requested Slot: {time_slot.start_time} - {time_slot.end_time}")
                    print(f"🇮🇳 Current Indian Time: {now_indian}")
                    print(f"📆 Today's Date: {today}")
                    print(f"🕐 Current Time: {current_time}")
                    print(f"👤 User: {request.user.email}")
                    print(f"{'='*60}\n")
                    
                    # ✅ VALIDATION 0: Check if date is in the past
                    if requested_date < today:
                        print(f"❌ VALIDATION FAILED: Past date")
                        messages.error(request, 'Cannot book demos for past dates. Please select a current or future date.')
                        return redirect(request.path + f'?demo={demo_id}')
                    
                    # ✅ VALIDATION 1: Check if user already has a booking for THIS SPECIFIC SLOT
                    existing_booking = DemoRequest.objects.filter(
                        user=request.user,
                        status__in=['pending', 'confirmed']
                    ).filter(
                        Q(confirmed_date=requested_date, confirmed_time_slot=time_slot) |
                        Q(requested_date=requested_date, requested_time_slot=time_slot, confirmed_date__isnull=True)
                    ).first()
                    
                    if existing_booking:
                        print(f"❌ VALIDATION FAILED: User already has this exact slot booked")
                        messages.error(
                            request, 
                            f'You already have a demo booking for {time_slot.start_time.strftime("%I:%M %p")} on {requested_date.strftime("%B %d, %Y")}. '
                            f'Please select a different time slot or date.'
                        )
                        return redirect(request.path + f'?demo={demo_id}')
                    
                    # ✅ VALIDATION 2: Check if requested time slot has ENDED (for today)
                    if requested_date == today:
                        # ✅ NEW LOGIC: Check if slot has ENDED (current time >= END time)
                        if current_time >= time_slot.end_time:
                            print(f"❌ VALIDATION FAILED: Slot has ended")
                            print(f"   Slot ends at: {time_slot.end_time}")
                            print(f"   Current time: {current_time}")
                            
                            messages.error(
                                request,
                                f'The time slot {time_slot.start_time.strftime("%I:%M %p")} - '
                                f'{time_slot.end_time.strftime("%I:%M %p")} has already ended '
                                f'(Current time: {current_time.strftime("%I:%M %p")}). '
                                f'Please select a future time slot.'
                            )
                            return redirect(request.path + f'?demo={demo_id}')
                        
                        # ✅ Check if slot is starting within 30 minutes (but hasn't started yet)
                        slot_start_datetime = indian_tz.localize(
                            datetime.combine(requested_date, time_slot.start_time)
                        )
                        current_datetime = now_indian
                        
                        time_until_start = (slot_start_datetime - current_datetime).total_seconds() / 60
                        
                        print(f"\n🔍 STARTING SOON CHECK:")
                        print(f"   Slot start: {slot_start_datetime}")
                        print(f"   Current: {current_datetime}")
                        print(f"   Time until start: {time_until_start:.2f} minutes")
                        
                        # ✅ Only block if starting within 30 minutes AND hasn't started yet
                        if 0 < time_until_start < 30:
                            print(f"❌ VALIDATION FAILED: Slot starting within 30 minutes ({time_until_start:.2f} min)")
                            messages.error(
                                request,
                                f'Cannot book slots starting within 30 minutes. '
                                f'The slot at {time_slot.start_time.strftime("%I:%M %p")} is starting in {int(time_until_start)} minutes. '
                                f'Please select a slot starting at least 30 minutes from now.'
                            )
                            return redirect(request.path + f'?demo={demo_id}')
                        elif time_until_start <= 0:
                            # Slot has already started - but check if it hasn't ended
                            if current_time < time_slot.end_time:
                                # Slot is in progress - ALLOW BOOKING!
                                print(f"✅ Slot in progress but still bookable (ends at {time_slot.end_time})")
                            else:
                                # This case should have been caught above
                                print(f"❌ Slot has ended")
                                messages.error(
                                    request,
                                    f'The time slot has already ended. Please select a future time slot.'
                                )
                                return redirect(request.path + f'?demo={demo_id}')
                        else:
                            print(f"✅ STARTING SOON CHECK PASSED: {time_until_start:.2f} minutes until start")
                    
                    # ✅ VALIDATION 3: Check if slot is already fully booked
                    existing_bookings = DemoRequest.objects.filter(
                        status__in=['pending', 'confirmed']
                    ).filter(
                        Q(confirmed_date=requested_date, confirmed_time_slot=time_slot) |
                        Q(requested_date=requested_date, requested_time_slot=time_slot, confirmed_date__isnull=True)
                    ).count()
                    
                    max_bookings_per_slot = 1
                    
                    if existing_bookings >= max_bookings_per_slot:
                        print(f"❌ VALIDATION FAILED: Slot is fully booked ({existing_bookings}/{max_bookings_per_slot})")
                        messages.error(
                            request,
                            f'Sorry, the time slot {time_slot.start_time.strftime("%I:%M %p")} is already fully booked. '
                            f'Please select a different time slot.'
                        )
                        return redirect(request.path + f'?demo={demo_id}')
                    
                    # ✅ VALIDATION 4: Check if date is Sunday
                    if requested_date.weekday() == 6:
                        print(f"❌ VALIDATION FAILED: Sunday selected")
                        messages.error(request, 'Demo sessions are not available on Sundays.')
                        return redirect(request.path + f'?demo={demo_id}')
                    
                    # ✅ All validations passed - Create booking
                    print(f"\n{'='*60}")
                    print(f"✅ ALL VALIDATIONS PASSED - CREATING BOOKING")
                    print(f"{'='*60}\n")
                    
                    demo_request = DemoRequest.objects.create(
                        user=request.user,
                        demo=selected_demo,
                        requested_date=requested_date,
                        requested_time_slot=time_slot,
                        notes=notes,
                        business_category=request.user.business_category,
                        business_subcategory=request.user.business_subcategory,
                        country_region=request.user.country_code
                    )
                    
                    print(f"✅ BOOKING CREATED: #{demo_request.id}")
                    
                    # Log activity
                    try:
                        from customers.models import CustomerActivity
                        CustomerActivity.objects.create(
                            user=request.user,
                            activity_type='demo_request',
                            description=f'Requested demo: {selected_demo.title} on {requested_date.strftime("%B %d, %Y")}',
                            ip_address=request.META.get('REMOTE_ADDR', ''),
                            user_agent=request.META.get('HTTP_USER_AGENT', ''),
                            metadata={
                                'demo_id': selected_demo.id,
                                'demo_title': selected_demo.title,
                                'requested_date': requested_date_str,
                                'time_slot': f"{time_slot.start_time.strftime('%I:%M %p')} - {time_slot.end_time.strftime('%I:%M %p')}"
                            }
                        )
                    except Exception as e:
                        print(f"⚠️ Activity logging error: {e}")
                    
                    messages.success(
                        request, 
                        f'Demo request for "{selected_demo.title}" submitted successfully! '
                        f'Reference ID: #{demo_request.id}. We will confirm your booking within 24 hours.'
                    )
                    return redirect('customers:demo_requests')
                    
                except TimeSlot.DoesNotExist:
                    print(f"❌ ERROR: Invalid time slot")
                    messages.error(request, 'Invalid time slot selected.')
                    return redirect(request.path + f'?demo={demo_id}')
                except ValueError as e:
                    print(f"❌ ERROR: Invalid date format - {str(e)}")
                    messages.error(request, f'Invalid date format: {str(e)}')
                    return redirect(request.path + f'?demo={demo_id}')
                except Exception as e:
                    print(f"❌ ERROR: Unexpected error - {str(e)}")
                    messages.error(request, f'An error occurred: {str(e)}')
                    import traceback
                    traceback.print_exc()
                    return redirect(request.path + f'?demo={demo_id}')
            
            # ===== GET - Show specific demo booking form =====
            time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
            
            from datetime import date, timedelta
            today = date.today()
            max_date = today + timedelta(days=30)
            
            context = get_customer_context(request.user)
            context.update({
                'selected_demo': selected_demo,
                'time_slots': time_slots,
                'min_date': today.isoformat(),
                'max_date': max_date.isoformat(),
            })
            
            return render(request, 'customers/request_demo_specific.html', context)
            
        except Exception as e:
            messages.error(request, 'An error occurred. Please try again.')
            print(f"❌ Error in request_demo (specific): {e}")
            import traceback
            traceback.print_exc()
            return redirect('customers:browse_demos')
    
    # ===== GENERAL SERVICE REQUEST FORM =====
    if request.method == 'POST':
        business_category_id = request.POST.get('business_category')
        business_subcategory_id = request.POST.get('business_subcategory', '')
        requested_date_str = request.POST.get('requested_date')
        time_slot_id = request.POST.get('time_slot_id')
        notes = request.POST.get('notes', '').strip()
        
        try:
            import pytz
            
            requested_date = datetime.strptime(requested_date_str, '%Y-%m-%d').date()
            time_slot = TimeSlot.objects.get(id=time_slot_id, is_active=True)
            category = BusinessCategory.objects.get(id=business_category_id)
            
            indian_tz = pytz.timezone('Asia/Kolkata')
            now_utc = timezone.now()
            now_indian = now_utc.astimezone(indian_tz)
            
            today = now_indian.date()
            current_time = now_indian.time()
            
            if requested_date < today:
                messages.error(request, 'Cannot book demos for past dates.')
                return redirect('customers:request_demo')
            
            # Same validation logic as above for general service
            if requested_date == today:
                if current_time >= time_slot.end_time:
                    messages.error(request, f'The time slot has already ended. Please select a future time slot.')
                    return redirect('customers:request_demo')
                
                slot_start_datetime = indian_tz.localize(datetime.combine(requested_date, time_slot.start_time))
                current_datetime = now_indian
                time_until_start = (slot_start_datetime - current_datetime).total_seconds() / 60
                
                if 0 < time_until_start < 30:
                    messages.error(request, 'Cannot book slots starting within 30 minutes.')
                    return redirect('customers:request_demo')
            
            if requested_date.weekday() == 6:
                messages.error(request, 'Demo sessions are not available on Sundays.')
                return redirect('customers:request_demo')
            
            # Create booking (rest of the code remains same)
            generic_demo, created = Demo.objects.get_or_create(
                slug='demo-consultation',
                defaults={
                    'title': 'Demo Consultation',
                    'description': 'General service consultation',
                    'is_active': True,
                    'demo_type': 'overview',
                }
            )
            
            demo_request = DemoRequest.objects.create(
                user=request.user,
                demo=generic_demo,
                requested_date=requested_date,
                requested_time_slot=time_slot,
                notes=notes,
                business_category=category,
                country_region=request.user.country_code
            )
            
            messages.success(request, f'Demo request submitted! Reference: #{demo_request.id}')
            return redirect('customers:demo_requests')
            
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return redirect('customers:request_demo')
    
    # ===== GET - Show general service request form =====
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    from datetime import date, timedelta
    today = date.today()
    max_date = today + timedelta(days=30)
    
    context = get_customer_context(request.user)
    context.update({
        'business_categories': business_categories,
        'time_slots': time_slots,
        'min_date': today.isoformat(),
        'max_date': max_date.isoformat(),
    })
    
    return render(request, 'customers/request_service.html', context)

@login_required
def enquiries(request):
    """Customer's business enquiries with status filtering"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '').strip()
    
    # Base queryset - Get user's enquiries
    enquiries = BusinessEnquiry.objects.filter(
        user=request.user
    ).select_related('category', 'assigned_to').prefetch_related('responses')
    
    # Apply status filter if provided
    if status_filter and status_filter in dict(BusinessEnquiry.STATUS_CHOICES):
        enquiries = enquiries.filter(status=status_filter)
    
    # Order by creation date (newest first)
    enquiries = enquiries.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(enquiries, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get context
    context = get_customer_context(request.user)
    
    # Calculate status counts
    all_enquiries = BusinessEnquiry.objects.filter(user=request.user)
    status_counts = {
        'total': all_enquiries.count(),
        'open': all_enquiries.filter(status='open').count(),
        'in_progress': all_enquiries.filter(status='in_progress').count(),
        'answered': all_enquiries.filter(status='answered').count(),
        'closed': all_enquiries.filter(status='closed').count(),
    }
    
    context.update({
        'page_obj': page_obj,
        'status_choices': BusinessEnquiry.STATUS_CHOICES,
        'current_status': status_filter,
        'status_counts': status_counts,
        'total_enquiries': status_counts['total'],
        'open_enquiries': status_counts['open'],
        'in_progress_enquiries': status_counts['in_progress'],
        'answered_enquiries': status_counts['answered'],
        'closed_enquiries': status_counts['closed'],
    })
    
    return render(request, 'customers/enquiries.html', context)

@login_required
def send_enquiry(request):
    """Send a business enquiry with business category selection"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    if request.method == 'POST':
        # Get form data
        business_category_id = request.POST.get('business_category')
        business_subcategory_id = request.POST.get('business_subcategory', '')
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        # Validation
        if not business_category_id:
            messages.error(request, 'Please select a business category.')
            return redirect('customers:send_enquiry')
        
        if not message or len(message) < 10:
            messages.error(request, 'Message must be at least 10 characters long.')
            return redirect('customers:send_enquiry')
        
        try:
            category = BusinessCategory.objects.get(id=business_category_id)
            
            # Build enquiry subject
            enquiry_subject = subject if subject else f"Business Enquiry - {category.name}"
            if business_subcategory_id:
                subcategory = BusinessSubCategory.objects.get(id=business_subcategory_id)
                enquiry_subject += f" ({subcategory.name})"
            
            # Build detailed message
            enquiry_message = f"""Business Category: {category.name}
"""
            if business_subcategory_id:
                enquiry_message += f"Subcategory: {subcategory.name}\n"
            
            enquiry_message += f"""

Customer Message:
{message}
"""
            
            # Create enquiry
            enquiry = BusinessEnquiry.objects.create(
                user=request.user,
                first_name=request.user.first_name,
                last_name=request.user.last_name,
                business_email=request.user.email,
                mobile=request.user.mobile,
                country_code=request.user.country_code,
                job_title=request.user.job_title,
                organization=request.user.organization,
                subject=enquiry_subject,
                message=enquiry_message
            )
            
            messages.success(request, f'Enquiry submitted successfully! Reference ID: {enquiry.enquiry_id}')
            return redirect('customers:enquiries')
            
        except BusinessCategory.DoesNotExist:
            messages.error(request, 'Invalid business category selected.')
            return redirect('customers:send_enquiry')
    
    # Get business categories for the form
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    context = get_customer_context(request.user)
    context.update({
        'business_categories': business_categories,
    })
    
    return render(request, 'customers/send_enquiry.html', context)

@login_required
def contact_sales(request):
    """Contact sales team"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        priority = request.POST.get('priority', 'normal')
        
        # Validation
        if not subject or len(subject) < 5:
            messages.error(request, 'Subject must be at least 5 characters long.')
            return redirect('customers:contact_sales')
        
        if not message or len(message) < 20:
            messages.error(request, 'Message must be at least 20 characters long.')
            return redirect('customers:contact_sales')
        
        # Create contact message
        from core.models import ContactMessage
        contact_msg = ContactMessage.objects.create(
            name=request.user.full_name,
            email=request.user.email,
            phone=request.user.full_mobile,
            company=request.user.organization,
            subject=subject,
            message=message,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        messages.success(request, 'Message sent to sales team! We will contact you within 24 hours.')
        return redirect('customers:dashboard')
    
    context = get_customer_context(request.user)
    return render(request, 'customers/contact_sales.html', context)

@login_required
def notifications(request):
    """Customer notifications - FIXED VERSION"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    notification_type = request.GET.get('type', '').strip()
    
    notifications_qs = Notification.objects.filter(user=request.user)
    
    if notification_type == 'unread':
        notifications_qs = notifications_qs.filter(is_read=False)
    elif notification_type and notification_type != 'all':
        notifications_qs = notifications_qs.filter(notification_type=notification_type)
    
    notifications_qs = notifications_qs.order_by('is_read', '-created_at')
    
    paginator = Paginator(notifications_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all notification types with counts - FIXED
    from django.db.models import Count
    type_data = Notification.objects.filter(
        user=request.user
    ).values('notification_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Create a list of tuples (type, count) instead of dict
    available_types = [(item['notification_type'], item['count']) for item in type_data]
    
    context = get_customer_context(request.user)
    context.update({
        'page_obj': page_obj,
        'current_filter': notification_type,
        'available_types': available_types,  # Now list of tuples
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
    })
    
    return render(request, 'customers/notifications.html', context)

@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Mark single notification as read"""
    try:
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            user=request.user
        )
        
        if not notification.is_read:
            notification.mark_as_read()
            
        return JsonResponse({
            'success': True,
            'message': 'Notification marked as read'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Failed to mark notification as read'
        }, status=500)

@login_required  
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    try:
        # Only mark unread notifications
        updated_count = Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'count': updated_count,
            'message': f'{updated_count} notification(s) marked as read'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Failed to mark notifications as read'
        }, status=500)

# AJAX Views
@login_required
@csrf_exempt
@require_http_methods(["POST"])
def submit_demo_feedback(request, demo_id):
    """Submit feedback for a demo - FIXED VERSION"""
    if not request.user.is_approved:
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    try:
        # Get the demo
        demo = get_object_or_404(Demo, id=demo_id, is_active=True)
        
        # Check if user can access this demo
        if not demo.can_customer_access(request.user):
            return JsonResponse({'error': 'Not authorized'}, status=403)
        
        # Parse JSON data
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        
        feedback_text = data.get('feedback', '').strip()
        rating = data.get('rating')
        
        # Validate feedback
        if not feedback_text:
            return JsonResponse({'error': 'Feedback text is required'}, status=400)
        
        if len(feedback_text) < 5:
            return JsonResponse({'error': 'Feedback must be at least 5 characters long'}, status=400)
        
        # Validate rating if provided
        if rating is not None:
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    return JsonResponse({'error': 'Rating must be between 1 and 5'}, status=400)
            except (ValueError, TypeError):
                rating = None
        
        # Check if user already submitted feedback
        existing_feedback = DemoFeedback.objects.filter(
            demo=demo, 
            user=request.user
        ).first()
        
        if existing_feedback:
            # Update existing feedback
            existing_feedback.feedback_text = feedback_text
            existing_feedback.rating = rating
            existing_feedback.is_approved = False  # Requires re-approval
            existing_feedback.save()
            
            message = 'Feedback updated successfully! It will be reviewed by our team.'
        else:
            # Create new feedback
            feedback = DemoFeedback.objects.create(
                demo=demo,
                user=request.user,
                feedback_text=feedback_text,
                rating=rating,
                is_approved=False  # Requires admin approval
            )
            
            message = 'Feedback submitted successfully! It will be reviewed by our team.'
        
        # Log activity
        try:
            from .models import CustomerActivity
            CustomerActivity.objects.create(
                user=request.user,
                activity_type='demo_feedback',
                description=f'Submitted feedback for demo: {demo.title}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'demo_id': demo.id,
                    'demo_title': demo.title,
                    'rating': rating,
                    'feedback_length': len(feedback_text)
                }
            )
        except Exception as e:
            print(f"Activity logging error: {e}")
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Demo.DoesNotExist:
        return JsonResponse({'error': 'Demo not found'}, status=404)
    except Exception as e:
        print(f"Error submitting feedback: {e}")
        return JsonResponse({
            'error': 'An error occurred while submitting feedback'
        }, status=500) 


@login_required
@require_http_methods(["POST"])
def cancel_demo_request(request, request_id):
    """Cancel a demo request with reason - UPDATED WITH ADMIN NOTIFICATION"""
    if not request.user.is_approved:
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    try:
        demo_request = get_object_or_404(
            DemoRequest, 
            id=request_id, 
            user=request.user,
            status__in=['pending', 'confirmed']
        )
        
        # Parse JSON data
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        details = data.get('details', '').strip()
        
        if not reason:
            return JsonResponse({
                'success': False,
                'error': 'Cancellation reason is required'
            }, status=400)
        
        # Update status and cancellation info
        demo_request.status = 'cancelled'
        demo_request.cancellation_reason = reason
        demo_request.cancellation_details = details
        demo_request.cancelled_at = timezone.now()
        
        # Update notes for backward compatibility
        reason_display = dict([
            ('scheduling_conflict', 'Scheduling Conflict'),
            ('requirements_change', 'Change in Requirements'),
            ('found_alternative', 'Found Alternative Solution'),
            ('no_longer_interested', 'No Longer Interested'),
            ('other', 'Other Reasons'),
        ]).get(reason, reason)
        
        cancel_note = f"[CANCELLED BY CUSTOMER] Reason: {reason_display}"
        if details:
            cancel_note += f"\nDetails: {details}"
        
        if demo_request.notes:
            demo_request.notes = f"{cancel_note}\n\n--- Previous Notes ---\n{demo_request.notes}"
        else:
            demo_request.notes = cancel_note
        
        demo_request.save()
        
        # ✅ NEW: Send notification to admins
        try:
            from notifications.services import NotificationService
            NotificationService.notify_admin_demo_request_cancelled(
                demo_request=demo_request,
                cancelled_by_customer=True,
                send_email=True
            )
            print(f"✅ Admin notifications sent for cancellation of request #{demo_request.id}")
        except Exception as e:
            print(f"⚠️ Error sending admin notifications: {e}")
            import traceback
            traceback.print_exc()
        
        # Log customer activity
        try:
            CustomerActivity.objects.create(
                user=request.user,
                activity_type='demo_request_cancelled',
                description=f'Cancelled demo request for: {demo_request.demo.title}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'demo_id': demo_request.demo.id,
                    'demo_title': demo_request.demo.title,
                    'request_id': demo_request.id,
                    'cancellation_reason': reason,
                    'cancellation_details': details,
                }
            )
        except Exception as e:
            print(f"⚠️ Activity logging error: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Demo request cancelled successfully!'
        })
        
    except DemoRequest.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Demo request not found or cannot be cancelled'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid request data'
        }, status=400)
    except Exception as e:
        print(f"❌ Error cancelling demo request: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while cancelling the request'
        }, status=500)

@login_required
@require_http_methods(["GET"])
def ajax_subcategories(request, category_id):
    """AJAX endpoint to get subcategories"""
    subcategories = BusinessSubCategory.objects.filter(
        category_id=category_id,
        is_active=True
    ).order_by('sort_order', 'name')
    
    data = {
        'subcategories': [
            {
                'id': sub.id,
                'name': sub.name,
            }
            for sub in subcategories
        ]
    }
    
    return JsonResponse(data)


@login_required
@require_http_methods(["GET"])
def ajax_demos_by_category(request):
    """AJAX endpoint to get demos by category/subcategory"""
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory', '')
    
    demos = Demo.objects.filter(is_active=True)
    
    if category_id:
        demos = demos.filter(
            Q(target_business_categories__id=category_id) |
            Q(target_business_categories__isnull=True)
        )
    
    if subcategory_id:
        demos = demos.filter(
            Q(target_business_subcategories__id=subcategory_id) |
            Q(target_business_subcategories__isnull=True)
        )
    
    demos = demos.distinct().order_by('-is_featured', 'sort_order', '-created_at')
    
    data = {
        'demos': [
            {
                'id': demo.id,
                'title': demo.title,
                'thumbnail': demo.thumbnail.url if demo.thumbnail else None,
                'category': demo.primary_business_category.name if demo.primary_business_category else None,
                'subcategories': [sub.name for sub in demo.target_business_subcategories.all()[:2]],
                'views': demo.views_count,
            }
            for demo in demos
        ]
    }
    
    return JsonResponse(data)

@login_required
@require_http_methods(["GET"])
def ajax_demo_detail(request, demo_id):
    """AJAX endpoint to get single demo details"""
    try:
        demo = Demo.objects.get(id=demo_id, is_active=True)
        
        data = {
            'demo': {
                'id': demo.id,
                'title': demo.title,
                'category_id': demo.primary_business_category.id if demo.primary_business_category else None,
            }
        }
        
        return JsonResponse(data)
    except Demo.DoesNotExist:
        return JsonResponse({'error': 'Demo not found'}, status=404)

@login_required
@require_http_methods(["GET"])
def ajax_check_slot_availability(request):
    """
    AJAX endpoint to check time slot availability for a specific date
    ✅ NEW LOGIC: Slot becomes unavailable only after END time passes
    """
    try:
        requested_date = request.GET.get('date')
        demo_id = request.GET.get('demo_id')
        
        if not requested_date:
            return JsonResponse({'success': False, 'error': 'Date is required'}, status=400)
        
        try:
            check_date = datetime.strptime(requested_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid date format'}, status=400)
        
        if check_date.weekday() == 6:
            return JsonResponse({
                'success': False,
                'available': False,
                'reason': 'sunday',
                'message': 'Demo sessions are not available on Sundays'
            })
        
        import pytz
        indian_tz = pytz.timezone('Asia/Kolkata')
        now_utc = timezone.now()
        now_indian = now_utc.astimezone(indian_tz)
        
        today = now_indian.date()
        current_time = now_indian.time()
        
        print(f"🕐 Current UTC time: {now_utc}")
        print(f"🇮🇳 Current Indian time: {now_indian}")
        print(f"📅 Today: {today}")
        print(f"⏰ Current time: {current_time}")
        
        if check_date < today:
            return JsonResponse({
                'success': False,
                'available': False,
                'reason': 'past',
                'message': 'Cannot book demos for past dates'
            })
        
        max_date = today + timedelta(days=30)
        if check_date > max_date:
            return JsonResponse({
                'success': False,
                'available': False,
                'reason': 'too_far',
                'message': 'Cannot book demos more than 30 days in advance'
            })
        
        all_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
        
        if not all_slots.exists():
            return JsonResponse({'success': False, 'message': 'No time slots configured'})
        
        user_existing_bookings = DemoRequest.objects.filter(
            user=request.user,
            status__in=['pending', 'confirmed']
        ).filter(
            Q(confirmed_date=check_date) | 
            Q(requested_date=check_date, confirmed_date__isnull=True)
        ).select_related('requested_time_slot', 'confirmed_time_slot')
        
        confirmed_bookings = DemoRequest.objects.filter(
            Q(confirmed_date=check_date) | 
            Q(requested_date=check_date, confirmed_date__isnull=True),
            status__in=['pending', 'confirmed']
        ).exclude(
            user=request.user
        ).select_related('demo', 'user', 'confirmed_time_slot', 'requested_time_slot')
        
        slots_data = []
        max_bookings_per_slot = 1
        is_today = check_date == today
        
        for slot in all_slots:
            is_past_slot = False
            is_starting_soon = False
            
            if is_today:
                # ✅ NEW LOGIC: Check if current time is PAST the END time (slot finished)
                # If current time >= END time → Slot is over
                # If current time < END time → Slot is still bookable (even if started)
                
                if current_time >= slot.end_time:
                    # Slot has ENDED - mark as past
                    is_past_slot = True
                    print(f"⏰ Slot {slot.start_time}-{slot.end_time} - ENDED (current: {current_time})")
                else:
                    # Slot has NOT ended yet
                    # Check if slot is starting within 30 minutes
                    slot_start_datetime = indian_tz.localize(
                        datetime.combine(check_date, slot.start_time)
                    )
                    current_datetime = now_indian
                    time_until_start = (slot_start_datetime - current_datetime).total_seconds() / 60
                    
                    print(f"⏰ Slot {slot.start_time}-{slot.end_time}: {time_until_start:.2f} min until start")
                    
                    # ✅ NEW: Only block if starting within 30 minutes AND hasn't started yet
                    if 0 < time_until_start < 30:
                        is_starting_soon = True
                        is_past_slot = True  # Make unselectable
                        print(f"   ⚠️ Starting soon ({time_until_start:.2f} min)")
                    elif time_until_start <= 0:
                        # Slot already started but not ended - still bookable!
                        print(f"   ✅ Slot in progress, still bookable")
            
            slot_bookings = confirmed_bookings.filter(
                Q(confirmed_time_slot=slot) | 
                Q(requested_time_slot=slot, confirmed_time_slot__isnull=True)
            )
            
            confirmed_count = slot_bookings.count()
            
            user_booked_this_slot = False
            for booking in user_existing_bookings:
                user_slot = booking.confirmed_time_slot or booking.requested_time_slot
                if user_slot and user_slot.id == slot.id:
                    user_booked_this_slot = True
                    break
            
            available_spots = max_bookings_per_slot - confirmed_count
            
            # Determine status
            if user_booked_this_slot:
                status = 'already_booked'
                is_available = False
                status_message = 'Your Booking'
            elif is_past_slot and not is_starting_soon:
                status = 'past'
                is_available = False
                status_message = 'Time Passed'
            elif is_starting_soon:
                status = 'starting_soon'
                is_available = False
                status_message = 'Starting Soon'
            elif available_spots <= 0:
                status = 'full'
                is_available = False
                status_message = 'Fully Booked'
            else:
                status = 'available'
                is_available = True
                status_message = 'Available'
            
            slot_info = {
                'id': slot.id,
                'start_time': slot.start_time.strftime('%I:%M %p'),
                'end_time': slot.end_time.strftime('%I:%M %p'),
                'slot_type': slot.get_slot_type_display(),
                'is_available': is_available,
                'confirmed_bookings': confirmed_count,
                'available_spots': max(0, available_spots),
                'total_capacity': max_bookings_per_slot,
                'occupancy_percentage': int((confirmed_count / max_bookings_per_slot) * 100) if confirmed_count > 0 else 0,
                'status': status,
                'status_message': status_message,
                'is_past': is_past_slot,
                'is_starting_soon': is_starting_soon,
                'user_already_booked': user_booked_this_slot
            }
            
            slots_data.append(slot_info)
        
        user_booking_message = None
        if user_existing_bookings.exists():
            booked_slots = []
            for booking in user_existing_bookings:
                booked_slot = booking.confirmed_time_slot or booking.requested_time_slot
                booked_slots.append(f"{booked_slot.start_time.strftime('%I:%M %p')}")
            
            if len(booked_slots) == 1:
                user_booking_message = f"You have a booking at {booked_slots[0]}"
            else:
                user_booking_message = f"You have bookings at {', '.join(booked_slots)}"
        
        return JsonResponse({
            'success': True,
            'available': True,
            'date': requested_date,
            'day_name': check_date.strftime('%A'),
            'is_today': is_today,
            'slots': slots_data,
            'total_bookings': confirmed_bookings.count(),
            'user_has_booking': user_existing_bookings.exists(),
            'user_booking_message': user_booking_message,
            'message': f'{confirmed_bookings.count() + user_existing_bookings.count()} demos scheduled for {check_date.strftime("%B %d, %Y")}'
        })
        
    except Exception as e:
        print(f"❌ Error in ajax_check_slot_availability: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': 'Server error occurred',
            'details': str(e) if request.user.is_staff else None
        }, status=500)

@login_required
@require_http_methods(["GET"])
def ajax_get_booking_calendar(request):
    """
    Get booking calendar data for the next 30 days
    Shows which dates have heavy bookings
    """
    try:
        from django.utils import timezone
        from django.db.models import Count
        
        today = timezone.now().date()
        end_date = today + timedelta(days=30)
        
        # Get all bookings in date range grouped by date
        bookings = DemoRequest.objects.filter(
            Q(confirmed_date__gte=today, confirmed_date__lte=end_date) |
            Q(requested_date__gte=today, requested_date__lte=end_date, confirmed_date__isnull=True),
            status__in=['pending', 'confirmed']
        )
        
        # Build calendar data
        calendar_data = {}
        
        # Count bookings per date
        for booking in bookings:
            date_key = booking.confirmed_date or booking.requested_date
            if date_key:
                date_str = date_key.strftime('%Y-%m-%d')
                calendar_data[date_str] = calendar_data.get(date_str, 0) + 1
        
        # Add availability status
        calendar_with_status = {}
        max_daily_capacity = 4  # ✅ CHANGED: 4 slots * 1 booking per slot = 4 max
        
        for date_str, count in calendar_data.items():
            if count >= max_daily_capacity:
                status = 'full'
            elif count >= 3:
                status = 'busy'
            elif count >= 2:
                status = 'moderate'
            else:
                status = 'available'
            
            calendar_with_status[date_str] = {
                'count': count,
                'status': status
            }
        
        # Mark Sundays as unavailable
        current_date = today
        while current_date <= end_date:
            if current_date.weekday() == 6:  # Sunday
                date_str = current_date.strftime('%Y-%m-%d')
                calendar_with_status[date_str] = {
                    'count': 0,
                    'status': 'unavailable',
                    'reason': 'sunday'
                }
            current_date += timedelta(days=1)
        
        return JsonResponse({
            'success': True,
            'calendar': calendar_with_status,
            'today': today.strftime('%Y-%m-%d'),
            'max_date': end_date.strftime('%Y-%m-%d')
        })
        
    except Exception as e:
        print(f"❌ Error in ajax_get_booking_calendar: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': 'Server error occurred'
        }, status=500)



@csrf_exempt  # ✅ ADD THIS - Temporarily exempt for debugging
@require_POST
def log_security_violation(request):
    """
    AJAX endpoint to log security violations from frontend
    ✅ FIXED: Better error handling and CSRF handling
    """
    try:
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'User not authenticated'
            }, status=401)
        
        # Parse JSON body
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid JSON: {str(e)}'
            }, status=400)
        
        violation_type = data.get('violation_type', 'unknown')
        description = data.get('description', '')
        page_url = data.get('page_url', '')
        
        # Validation
        if not violation_type:
            return JsonResponse({
                'success': False,
                'error': 'violation_type is required'
            }, status=400)
        
        # Map violation types
        violation_type_mapping = {
            'devtools_detected': 'devtools_detected',
            'screen_recording': 'screen_recording',
            'copy_attempt': 'unauthorized_access',
            'clipboard_image': 'unauthorized_access',
            'multiple_focus_loss': 'suspicious_activity',
            'right_click_attempt': 'unauthorized_access',
            'keyboard_shortcut': 'unauthorized_access',
            'screenshot_attempt': 'unauthorized_access',
            'drag_attempt': 'unauthorized_access',
            'focus_loss_suspicious': 'suspicious_activity',
            'screenshot_tool_detected': 'suspicious_activity',
            'screen_recording_blocked': 'screen_recording',
            'screen_capture_blocked': 'screen_recording',
            'devtools_open': 'devtools_detected',
            'canvas_screenshot': 'unauthorized_access',
        }
        
        mapped_type = violation_type_mapping.get(
            violation_type, 
            'unauthorized_access'
        )
        
        # Create security violation record
        violation = SecurityViolation.objects.create(
            user=request.user,
            violation_type=mapped_type,
            description=f"{violation_type}: {description}",
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            page_url=page_url,
            referrer=request.META.get('HTTP_REFERER', ''),
        )
        
        # Log as customer activity (optional)
        try:
            log_customer_activity(
                user=request.user,
                activity_type='security_violation',
                description=description,
                request=request,
                violation_type=violation_type
            )
        except Exception as e:
            print(f"⚠️ Activity logging error: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Security violation logged',
            'violation_id': violation.id
        })
        
    except Exception as e:
        print(f"❌ Error in log_security_violation: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)