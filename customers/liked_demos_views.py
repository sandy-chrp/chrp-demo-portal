# customers/liked_demos_views.py - UPDATED WITH WEBGL SUPPORT
"""
Views for Liked Demos functionality
Handles all operations related to customer's liked/favorite videos
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, F, Count
from django.core.paginator import Paginator
from django.utils import timezone
from accounts.models import BusinessCategory, BusinessSubCategory
from demos.models import Demo, DemoLike, DemoView
from .views import get_customer_context

@login_required
def liked_demos(request):
    """
    Display all demos liked by the customer - WITH WEBGL SUPPORT
    Features: Search, Sort, Category Filter, Pagination, Access Control
    """
    # Check if user is approved
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    # Get user's business category and subcategory
    user_business_category = request.user.business_category
    user_business_subcategory = request.user.business_subcategory
    
    # Get filter parameters
    business_category_id = request.GET.get('business_category')
    business_subcategory_id = request.GET.get('business_subcategory')
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'recently_liked')
    
    # Get liked demo IDs for this user
    liked_demo_ids = DemoLike.objects.filter(
        user=request.user
    ).values_list('demo_id', flat=True)
    
    # Get all liked demos with proper prefetch
    demos_query = Demo.objects.filter(
        id__in=liked_demo_ids,
        is_active=True
    ).prefetch_related(
        'target_business_categories',
        'target_business_subcategories',
        'target_customers'
    ).select_related('created_by')
    
    # Filter by business category access and customer access
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
    if sort_by == 'recently_liked':
        # Sort by when user liked it (most recent first)
        like_dates = {
            like.demo_id: like.liked_at 
            for like in DemoLike.objects.filter(
                user=request.user,
                demo_id__in=demos.values_list('id', flat=True)
            )
        }
        demos_list = list(demos)
        demos_list.sort(key=lambda x: like_dates.get(x.id, timezone.now()), reverse=True)
        demos = demos_list
    elif sort_by == 'oldest_liked':
        like_dates = {
            like.demo_id: like.liked_at 
            for like in DemoLike.objects.filter(
                user=request.user,
                demo_id__in=demos.values_list('id', flat=True)
            )
        }
        demos_list = list(demos)
        demos_list.sort(key=lambda x: like_dates.get(x.id, timezone.now()))
        demos = demos_list
    elif sort_by == 'title':
        demos = demos.order_by('title')
    elif sort_by == 'most_viewed':
        demos = demos.order_by('-views_count')
    elif sort_by == 'most_liked':
        demos = demos.order_by('-likes_count')
    elif sort_by == 'newest':
        demos = demos.order_by('-created_at')
    
    # Get total count
    total_liked = len(demos) if isinstance(demos, list) else demos.count()
    
    # Pagination - 12 demos per page
    paginator = Paginator(demos, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get user's viewed demos
    user_views = DemoView.objects.filter(
        user=request.user
    ).values_list('demo_id', flat=True)
    
    # Calculate watched count from liked videos
    liked_demo_ids_list = list(liked_demo_ids)
    total_watched = len([vid for vid in user_views if vid in liked_demo_ids_list])
    
    # Get ALL business categories for filter dropdown
    business_categories = BusinessCategory.objects.filter(
        is_active=True
    ).order_by('sort_order', 'name')
    
    # Get ALL subcategories for dynamic filtering
    business_subcategories = BusinessSubCategory.objects.filter(
        is_active=True
    ).select_related('category').order_by('category__sort_order', 'sort_order', 'name')
    
    # Get common customer context
    context = get_customer_context(request.user)
    
    # Add liked demos specific context
    context.update({
        'page_obj': page_obj,
        'total_liked': total_liked,
        'business_categories': business_categories,
        'business_subcategories': business_subcategories,
        'current_business_category': int(business_category_id) if business_category_id else None,
        'current_business_subcategory': int(business_subcategory_id) if business_subcategory_id else None,
        'search_query': search_query,
        'sort_by': sort_by,
        'user_views': list(user_views),
        'total_watched': total_watched,
        'sort_options': [
            {'value': 'recently_liked', 'label': 'Recently Liked'},
            {'value': 'oldest_liked', 'label': 'Oldest Liked'},
            {'value': 'title', 'label': 'Title (A-Z)'},
            {'value': 'most_viewed', 'label': 'Most Viewed'},
            {'value': 'most_liked', 'label': 'Most Liked'},
            {'value': 'newest', 'label': 'Newest Videos'},
        ]
    })
    
    return render(request, 'customers/liked_demos.html', context)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def unlike_demo(request, demo_id):
    """
    AJAX endpoint to unlike/remove a demo from liked videos
    Returns JSON response
    """
    if not request.user.is_approved:
        return JsonResponse({
            'success': False,
            'error': 'Account not approved'
        }, status=403)
    
    try:
        # Get the demo
        demo = get_object_or_404(Demo, id=demo_id, is_active=True)
        
        # Check if user has access to this demo
        if not demo.can_customer_access(request.user):
            return JsonResponse({
                'success': False,
                'error': 'Demo not accessible'
            }, status=403)
        
        # Find and delete the like
        like_obj = DemoLike.objects.filter(
            demo=demo,
            user=request.user
        ).first()
        
        if like_obj:
            like_obj.delete()
            
            # Decrement likes count
            Demo.objects.filter(id=demo.id).update(
                likes_count=F('likes_count') - 1
            )
            
            # Get updated count
            demo.refresh_from_db()
            
            return JsonResponse({
                'success': True,
                'liked': False,
                'likes_count': demo.likes_count,
                'message': 'Video removed from your liked videos'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Video was not liked'
            }, status=400)
            
    except Demo.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Demo not found'
        }, status=404)
    except Exception as e:
        print(f"Error unliking demo: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to unlike video'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_liked_demos_count(request):
    """
    AJAX endpoint to get total count of liked demos
    """
    if not request.user.is_approved:
        return JsonResponse({'count': 0})
    
    try:
        count = DemoLike.objects.filter(user=request.user).count()
        return JsonResponse({
            'success': True,
            'count': count
        })
    except Exception as e:
        print(f"Error getting liked demos count: {e}")
        return JsonResponse({
            'success': False,
            'count': 0
        })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def clear_all_liked_demos(request):
    """
    AJAX endpoint to clear all liked demos for the user
    """
    if not request.user.is_approved:
        return JsonResponse({
            'success': False,
            'error': 'Not authorized'
        }, status=403)
    
    try:
        # Get all liked demo IDs
        liked_demo_ids = list(
            DemoLike.objects.filter(user=request.user).values_list('demo_id', flat=True)
        )
        
        count = len(liked_demo_ids)
        
        if count == 0:
            return JsonResponse({
                'success': False,
                'message': 'No liked videos to clear'
            })
        
        # Delete all likes
        DemoLike.objects.filter(user=request.user).delete()
        
        # Update likes count for all affected demos
        for demo_id in liked_demo_ids:
            Demo.objects.filter(id=demo_id).update(
                likes_count=F('likes_count') - 1
            )
        
        return JsonResponse({
            'success': True,
            'count': count,
            'message': f'{count} liked video{"s" if count != 1 else ""} cleared successfully'
        })
        
    except Exception as e:
        print(f"Error clearing liked demos: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to clear liked videos'
        }, status=500)