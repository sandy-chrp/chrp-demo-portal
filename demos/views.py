# demos/views.py - Fixed request handling
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

from .models import Demo, DemoCategory, DemoRequest, DemoView, DemoLike, DemoFeedback, TimeSlot
from .forms import DemoRequestForm, DemoFeedbackForm, DemoFilterForm
from accounts.models import CustomUser

@login_required
def demo_list_view(request):
    """Demo library with filtering and search"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    demos_list = Demo.objects.filter(is_active=True).select_related('category')
    
    # Get categories for filters
    categories = DemoCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    # Filtering
    category_filter = request.GET.get('category')
    search = request.GET.get('search')
    status = request.GET.get('status')
    
    if category_filter:
        category = get_object_or_404(DemoCategory, slug=category_filter, is_active=True)
        demos_list = demos_list.filter(category=category)
    
    if search:
        demos_list = demos_list.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )
    
    if status:
        if status == 'new':
            demos_list = demos_list.order_by('-created_at')
        elif status == 'popular':
            demos_list = demos_list.order_by('-views_count')
        elif status == 'liked':
            demos_list = demos_list.filter(demo_likes__user=request.user)
        elif status == 'watched':
            demos_list = demos_list.filter(demo_views__user=request.user)
    
    # Pagination
    paginator = Paginator(demos_list, 12)
    page_number = request.GET.get('page')
    demos = paginator.get_page(page_number)
    
    # Get user interactions
    user_views = set(DemoView.objects.filter(user=request.user).values_list('demo_id', flat=True))
    user_likes = set(DemoLike.objects.filter(user=request.user).values_list('demo_id', flat=True))
    
    context = {
        'demos': demos,
        'categories': categories,
        'category_filter': category_filter,
        'search': search,
        'status_filter': status,
        'user_views': user_views,
        'user_likes': user_likes,
    }
    
    return render(request, 'demos/list.html', context)

@login_required
def demo_detail_view(request, slug):
    """Demo detail view"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    demo = get_object_or_404(Demo, slug=slug, is_active=True)
    
    # Check if user has viewed
    user_has_viewed = DemoView.objects.filter(user=request.user, demo=demo).exists()
    
    # Check if user has liked
    user_has_liked = DemoLike.objects.filter(user=request.user, demo=demo).exists()
    
    # Get user feedback
    user_feedback = None
    try:
        user_feedback = DemoFeedback.objects.get(user=request.user, demo=demo)
    except DemoFeedback.DoesNotExist:
        pass
    
    # Get related demos
    related_demos = Demo.objects.filter(
        category=demo.category,
        is_active=True
    ).exclude(id=demo.id)[:4]
    
    context = {
        'demo': demo,
        'user_has_viewed': user_has_viewed,
        'user_has_liked': user_has_liked,
        'user_feedback': user_feedback,
        'related_demos': related_demos,
    }
    
    return render(request, 'demos/detail.html', context)

@login_required
def watch_demo_view(request, slug):
    """Watch demo video"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    demo = get_object_or_404(Demo, slug=slug, is_active=True)
    
    # Record view if not already viewed
    demo_view, created = DemoView.objects.get_or_create(
        user=request.user,
        demo=demo,
        defaults={'ip_address': get_client_ip(request)}
    )
    
    if created:
        # Increment view count
        Demo.objects.filter(id=demo.id).update(views_count=models.F('views_count') + 1)
    
    # Check if user has liked
    user_has_liked = DemoLike.objects.filter(user=request.user, demo=demo).exists()
    
    context = {
        'demo': demo,
        'user_has_liked': user_has_liked,
    }
    
    return render(request, 'demos/watch.html', context)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def like_demo_view(request, slug):
    """Toggle demo like via AJAX"""
    if not request.user.is_approved:
        return JsonResponse({'success': False, 'message': 'Account not approved'})
    
    demo = get_object_or_404(Demo, slug=slug, is_active=True)
    
    # Toggle like
    demo_like, created = DemoLike.objects.get_or_create(
        user=request.user,
        demo=demo
    )
    
    if not created:
        # Unlike
        demo_like.delete()
        liked = False
    else:
        # Like
        liked = True
    
    # Update like count
    likes_count = DemoLike.objects.filter(demo=demo).count()
    Demo.objects.filter(id=demo.id).update(likes_count=likes_count)
    
    return JsonResponse({
        'success': True,
        'liked': liked,
        'likes_count': likes_count
    })

@login_required
def demo_feedback_view(request, slug):
    """Submit feedback for demo"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    demo = get_object_or_404(Demo, slug=slug, is_active=True)
    
    # Get or create feedback
    feedback, created = DemoFeedback.objects.get_or_create(
        user=request.user,
        demo=demo
    )
    
    if request.method == 'POST':
        form = DemoFeedbackForm(request.POST, instance=feedback)
        if form.is_valid():
            form.save()
            messages.success(request, 'Thank you for your feedback!')
            return redirect('demos:detail', slug=demo.slug)
    else:
        form = DemoFeedbackForm(instance=feedback)
    
    context = {
        'demo': demo,
        'form': form,
        'feedback': feedback,
    }
    
    return render(request, 'demos/feedback.html', context)

@login_required
def request_demo_view(request, slug=None):
    """Request live demo session - Fixed to handle both cases"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    demo = None
    if slug:
        demo = get_object_or_404(Demo, slug=slug, is_active=True)
    
    if request.method == 'POST':
        form = DemoRequestForm(request.POST)
        # Pass user to form for validation
        form.user = request.user
        
        if form.is_valid():
            demo_request = form.save(commit=False)
            demo_request.user = request.user
            demo_request.save()
            
            messages.success(request, 'Demo request submitted successfully! We will contact you soon.')
            return redirect('demos:my_requests')
    else:
        form = DemoRequestForm()
        # Pre-select demo if provided
        if demo:
            form.fields['demo'].initial = demo
    
    context = {
        'form': form,
        'demo': demo,
    }
    
    return render(request, 'demos/request.html', context)

@login_required
def my_demo_requests_view(request):
    """User's demo requests"""
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    requests_list = DemoRequest.objects.filter(
        user=request.user
    ).select_related('demo', 'requested_time_slot').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(requests_list, 10)
    page_number = request.GET.get('page')
    requests = paginator.get_page(page_number)
    
    # Get status counts
    status_counts = DemoRequest.objects.filter(user=request.user).values('status').annotate(
        count=Count('status')
    ).order_by('status')
    
    context = {
        'requests': requests,
        'status_filter': status_filter,
        'status_counts': status_counts,
    }
    
    return render(request, 'demos/my_requests.html', context)

# Utility function
def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip