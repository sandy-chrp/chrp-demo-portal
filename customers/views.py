# customers/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.conf import settings
import json
from django.views.decorators.http import require_http_methods

from accounts.models import CustomUser
from demos.models import Demo, DemoCategory, DemoRequest, DemoView, DemoLike, DemoFeedback, TimeSlot
from enquiries.models import BusinessEnquiry, EnquiryCategory, EnquiryResponse
from notifications.models import Notification
from core.models import SiteSettings, ContactMessage


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

@login_required
def customer_dashboard(request):
    """Customer main dashboard"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    context = get_customer_context(request.user)
    
    # Additional dashboard stats
    context.update({
        'recent_demo_requests': DemoRequest.objects.filter(
            user=request.user
        ).order_by('-created_at')[:3],
        
        'recent_enquiries': BusinessEnquiry.objects.filter(
            user=request.user
        ).order_by('-created_at')[:3],
        
        # Featured demos
        'featured_demos': Demo.objects.filter(
            is_active=True,
            is_featured=True
        ).filter(
            Q(target_customers=request.user) | Q(target_customers__isnull=True)
        )[:4],
        
        # Quick stats for dashboard cards
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
    """Browse available demo videos"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    # Get filter parameters
    category_id = request.GET.get('category')
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'newest')
    
    # Base queryset - only demos user can access
    demos = Demo.objects.filter(is_active=True).filter(
        Q(target_customers=request.user) | Q(target_customers__isnull=True)
    )
    
    # Apply filters
    if category_id:
        demos = demos.filter(category_id=category_id)
    
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
    
    # Pagination
    paginator = Paginator(demos, 12)  # 12 demos per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get categories for filter
    categories = DemoCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    # Add user interaction data
    user_views = DemoView.objects.filter(user=request.user).values_list('demo_id', flat=True)
    user_likes = DemoLike.objects.filter(user=request.user).values_list('demo_id', flat=True)
    
    context = get_customer_context(request.user)
    context.update({
        'page_obj': page_obj,
        'categories': categories,
        'current_category': int(category_id) if category_id else None,
        'search_query': search_query,
        'sort_by': sort_by,
        'user_views': list(user_views),
        'user_likes': list(user_likes),
    })
    
    return render(request, 'customers/browse_demos.html', context)

@login_required
def demo_detail(request, slug):
    """Individual demo detail page with security restrictions"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    demo = get_object_or_404(Demo, slug=slug, is_active=True)
    
    # Check if user can access this demo
    if not demo.can_customer_access(request.user):
        raise Http404("Demo not found")
    
    # Record view
    demo_view, created = DemoView.objects.get_or_create(
        demo=demo,
        user=request.user,
        defaults={'ip_address': request.META.get('REMOTE_ADDR')}
    )
    
    if created:
        # Increment view count
        Demo.objects.filter(id=demo.id).update(views_count=F('views_count') + 1)
    
    # Get user interactions
    user_liked = DemoLike.objects.filter(demo=demo, user=request.user).exists()
    user_feedback = DemoFeedback.objects.filter(demo=demo, user=request.user).first()
    
    # Get approved feedbacks
    approved_feedbacks = DemoFeedback.objects.filter(
        demo=demo,
        is_approved=True
    ).order_by('-created_at')[:5]
    
    # Get related demos
    related_demos = Demo.objects.filter(
        category=demo.category,
        is_active=True
    ).filter(
        Q(target_customers=request.user) | Q(target_customers__isnull=True)
    ).exclude(id=demo.id)[:4]
    
    context = get_customer_context(request.user)
    context.update({
        'demo': demo,
        'user_liked': user_liked,
        'user_feedback': user_feedback,
        'approved_feedbacks': approved_feedbacks,
        'related_demos': related_demos,
        'can_request_demo': True,  # Customer can request live demo
    })
    
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
    
    # Base queryset - Get user's demo requests
    requests = DemoRequest.objects.filter(
        user=request.user
    ).select_related('demo', 'requested_time_slot', 'confirmed_time_slot')
    
    # Apply status filter if provided
    if status_filter and status_filter in dict(DemoRequest.STATUS_CHOICES):
        requests = requests.filter(status=status_filter)
    
    # Order by creation date (newest first)
    requests = requests.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get context
    context = get_customer_context(request.user)
    
    # Add status counts for better UX
    status_counts = {}
    all_requests = DemoRequest.objects.filter(user=request.user)
    
    # Calculate counts for each status
    for status_key, status_label in DemoRequest.STATUS_CHOICES:
        count = all_requests.filter(status=status_key).count()
        status_counts[status_key] = count
    
    # Total count
    status_counts['all'] = all_requests.count()
    
    context.update({
        'page_obj': page_obj,
        'status_choices': DemoRequest.STATUS_CHOICES,
        'current_status': status_filter,
        'status_counts': status_counts,
        'total_requests': status_counts['all'],
    })
    
    return render(request, 'customers/demo_requests.html', context)
@login_required
def request_demo(request):
    """Request a live demo session"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    if request.method == 'POST':
        demo_id = request.POST.get('demo_id')
        requested_date = request.POST.get('requested_date')
        time_slot_id = request.POST.get('time_slot_id')
        notes = request.POST.get('notes', '').strip()
        
        # Validation
        try:
            demo = Demo.objects.get(id=demo_id, is_active=True)
            if not demo.can_customer_access(request.user):
                raise Demo.DoesNotExist()
                
            time_slot = TimeSlot.objects.get(id=time_slot_id, is_active=True)
            
            # Create demo request
            demo_request = DemoRequest.objects.create(
                user=request.user,
                demo=demo,
                requested_date=requested_date,
                requested_time_slot=time_slot,
                notes=notes
            )
            
            messages.success(request, 'Demo request submitted successfully! We will contact you soon.')
            return redirect('customers:demo_requests')
            
        except (Demo.DoesNotExist, TimeSlot.DoesNotExist, ValueError):
            messages.error(request, 'Invalid demo request. Please try again.')
    
    # Get available demos
    available_demos = Demo.objects.filter(is_active=True).filter(
        Q(target_customers=request.user) | Q(target_customers__isnull=True)
    ).order_by('title')
    
    # Get time slots
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    context = get_customer_context(request.user)
    context.update({
        'available_demos': available_demos,
        'time_slots': time_slots,
    })
    
    return render(request, 'customers/request_demo.html', context)

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
    """Send a business enquiry"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    if request.method == 'POST':
        # Get form data
        category_id = request.POST.get('category_id')
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        
        # Validation
        if not message or len(message) < 10:
            messages.error(request, 'Message must be at least 10 characters long.')
            return redirect('customers:send_enquiry')
        
        # Create enquiry
        enquiry = BusinessEnquiry.objects.create(
            user=request.user,
            category_id=category_id if category_id else None,
            first_name=request.user.first_name,
            last_name=request.user.last_name,
            business_email=request.user.email,
            mobile=request.user.mobile,
            country_code=request.user.country_code,
            job_title=request.user.job_title,
            organization=request.user.organization,
            subject=subject,
            message=message
        )
        
        messages.success(request, f'Enquiry submitted successfully! Reference ID: {enquiry.enquiry_id}')
        return redirect('customers:enquiries')
    
    # Get enquiry categories
    categories = EnquiryCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    context = get_customer_context(request.user)
    context.update({
        'categories': categories,
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
    """Customer notifications"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    # Get filter type
    notification_type = request.GET.get('type', '').strip()
    
    # Base queryset
    notifications = Notification.objects.filter(user=request.user)
    
    # Apply filters
    if notification_type == 'unread':
        notifications = notifications.filter(is_read=False)
    elif notification_type and notification_type != 'all':
        notifications = notifications.filter(notification_type=notification_type)
    
    # Order by creation date
    notifications = notifications.order_by('-created_at')
    
    # Mark as read when viewing (optional)
    unread_notifications = notifications.filter(is_read=False)
    for notification in unread_notifications:
        notification.mark_as_read()
    
    # Pagination
    paginator = Paginator(notifications, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = get_customer_context(request.user)
    context.update({
        'page_obj': page_obj,
        'current_filter': notification_type,
    })
    
    return render(request, 'customers/notifications.html', context)


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    try:
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.mark_as_read()
        return JsonResponse({'success': True})
    except:
        return JsonResponse({'error': 'Failed to mark notification as read'}, status=500)

@login_required  
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    try:
        count = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return JsonResponse({'success': True, 'count': count})
    except:
        return JsonResponse({'error': 'Failed to mark notifications as read'}, status=500)

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
    """Cancel a demo request"""
    if not request.user.is_approved:
        return JsonResponse({'error': 'Not authorized'}, status=403)
    
    try:
        demo_request = get_object_or_404(
            DemoRequest, 
            id=request_id, 
            user=request.user,
            status='pending'  # Only pending requests can be cancelled
        )
        
        # Update status to cancelled
        demo_request.status = 'cancelled'
        demo_request.save()
        
        # Log activity (optional)
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
                    'request_id': demo_request.id
                }
            )
        except Exception as e:
            print(f"Activity logging error: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Demo request cancelled successfully!'
        })
        
    except DemoRequest.DoesNotExist:
        return JsonResponse({
            'error': 'Demo request not found or cannot be cancelled'
        }, status=404)
    except Exception as e:
        print(f"Error cancelling demo request: {e}")
        return JsonResponse({
            'error': 'An error occurred while cancelling the request'
        }, status=500)