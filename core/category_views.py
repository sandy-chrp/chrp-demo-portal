# core/category_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.utils.text import slugify
import json

from accounts.models import CustomUser
from demos.models import Demo, DemoCategory, DemoRequest
from enquiries.models import BusinessEnquiry

# Helper function to check if user is admin
def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@login_required
@user_passes_test(is_admin)
def admin_categories_view(request):
    """Admin category management with CRUD functionality"""
    categories_list = DemoCategory.objects.annotate(
        demo_count=Count('demos')
    ).order_by('sort_order', 'name')
    
    # Filtering
    search = request.GET.get('search')
    status_filter = request.GET.get('status')
    sort_by = request.GET.get('sort', 'sort_order')
    
    if search:
        categories_list = categories_list.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )
    
    if status_filter == 'active':
        categories_list = categories_list.filter(is_active=True)
    elif status_filter == 'inactive':
        categories_list = categories_list.filter(is_active=False)
    
    # Sorting
    if sort_by in ['name', '-name', 'sort_order', '-sort_order', '-demo_count']:
        categories_list = categories_list.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(categories_list, 15)
    page_number = request.GET.get('page')
    categories = paginator.get_page(page_number)
    
    # Statistics
    total_categories = DemoCategory.objects.count()
    active_categories = DemoCategory.objects.filter(is_active=True).count()
    total_demos_in_categories = Demo.objects.count()
    
    # Context for sidebar badges
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'categories': categories,
        'search': search,
        'status_filter': status_filter,
        'sort_by': sort_by,
        
        # Statistics
        'total_categories': total_categories,
        'active_categories': active_categories,
        'total_demos_in_categories': total_demos_in_categories,
        
        # Sidebar context
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/categories/list.html', context)

@login_required
@user_passes_test(is_admin)
def admin_add_category_view(request):
    """Add new demo category"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        icon = request.POST.get('icon', '')
        sort_order = request.POST.get('sort_order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        # Validation
        if not name:
            messages.error(request, 'Category name is required.')
        elif DemoCategory.objects.filter(name=name).exists():
            messages.error(request, f'Category "{name}" already exists.')
        else:
            try:
                category = DemoCategory.objects.create(
                    name=name,
                    description=description,
                    icon=icon,
                    sort_order=int(sort_order) if sort_order else 0,
                    is_active=is_active
                )
                messages.success(request, f'Category "{category.name}" has been created successfully!')
                return redirect('core:admin_categories')
            except Exception as e:
                messages.error(request, 'Error creating category. Please try again.')
    
    # Context for sidebar badges
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/categories/add.html', context)

@login_required
@user_passes_test(is_admin)
def admin_category_detail_view(request, category_id):
    """View category details"""
    category = get_object_or_404(DemoCategory, id=category_id)
    
    # Category statistics
    demo_count = Demo.objects.filter(category=category).count()
    active_demos = Demo.objects.filter(category=category, is_active=True).count()
    total_views = Demo.objects.filter(category=category).aggregate(
        total=Count('demo_views')
    )['total'] or 0
    
    # Recent demos in this category
    recent_demos = Demo.objects.filter(category=category).select_related('created_by').order_by('-created_at')[:5]
    
    # Context for sidebar badges
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'category': category,
        'demo_count': demo_count,
        'active_demos': active_demos,
        'total_views': total_views,
        'recent_demos': recent_demos,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/categories/detail.html', context)

@login_required
@user_passes_test(is_admin)
def admin_edit_category_view(request, category_id):
    """Edit category details"""
    category = get_object_or_404(DemoCategory, id=category_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        icon = request.POST.get('icon', '')
        sort_order = request.POST.get('sort_order', 0)
        is_active = request.POST.get('is_active') == 'on'
        
        # Validation
        if not name:
            messages.error(request, 'Category name is required.')
        elif DemoCategory.objects.filter(name=name).exclude(id=category.id).exists():
            messages.error(request, f'Category "{name}" already exists.')
        else:
            try:
                category.name = name
                category.description = description
                category.icon = icon
                category.sort_order = int(sort_order) if sort_order else 0
                category.is_active = is_active
                category.save()
                
                messages.success(request, f'Category "{category.name}" has been updated successfully!')
                return redirect('core:admin_category_detail', category_id=category.id)
            except Exception as e:
                messages.error(request, 'Error updating category. Please try again.')
    
    # Category statistics
    demo_count = Demo.objects.filter(category=category).count()
    active_demos = Demo.objects.filter(category=category, is_active=True).count()
    total_views = Demo.objects.filter(category=category).aggregate(
        total=Count('demo_views')
    )['total'] or 0
    
    # Context for sidebar badges
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'category': category,
        'demo_count': demo_count,
        'active_demos': active_demos,
        'total_views': total_views,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/categories/edit.html', context)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_delete_category_view(request, category_id):
    """Delete category"""
    category = get_object_or_404(DemoCategory, id=category_id)
    
    # Check if category has demos
    demo_count = Demo.objects.filter(category=category).count()
    
    if demo_count > 0:
        return JsonResponse({
            'success': False,
            'message': f'Cannot delete category "{category.name}". It contains {demo_count} demo(s). Please move or delete the demos first.'
        })
    
    try:
        category_name = category.name
        category.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Category "{category_name}" has been deleted successfully.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error deleting category. Please try again.'
        })

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_toggle_category_status_view(request, category_id):
    """Toggle category active/inactive status"""
    category = get_object_or_404(DemoCategory, id=category_id)
    
    try:
        data = json.loads(request.body)
        activate = data.get('activate', not category.is_active)
        
        old_status = category.is_active
        category.is_active = activate
        category.save()
        
        status = "activated" if activate else "deactivated"
        
        return JsonResponse({
            'success': True,
            'message': f'Category "{category.name}" has been {status}.',
            'is_active': category.is_active,
            'changed': old_status != category.is_active
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error updating category status. Please try again.'
        })

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_bulk_category_actions_view(request):
    """Handle bulk category actions"""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        category_ids = data.get('category_ids', [])
        
        if not category_ids:
            return JsonResponse({
                'success': False,
                'message': 'No categories selected.'
            })
        
        categories = DemoCategory.objects.filter(id__in=category_ids)
        count = categories.count()
        
        if count == 0:
            return JsonResponse({
                'success': False,
                'message': 'No valid categories found.'
            })
        
        if action == 'activate':
            updated = categories.update(is_active=True)
            message = f'{updated} categories have been activated.'
        elif action == 'deactivate':
            updated = categories.update(is_active=False)
            message = f'{updated} categories have been deactivated.'
        elif action == 'delete':
            # Check if any category has demos
            categories_with_demos = []
            deletable_categories = []
            
            for category in categories:
                demo_count = Demo.objects.filter(category=category).count()
                if demo_count > 0:
                    categories_with_demos.append(f'{category.name} ({demo_count} demos)')
                else:
                    deletable_categories.append(category)
            
            if categories_with_demos:
                return JsonResponse({
                    'success': False,
                    'message': f'Cannot delete categories that contain demos: {", ".join(categories_with_demos)}. Please move or delete the demos first.'
                })
            
            # Delete only categories without demos
            deleted_count = len(deletable_categories)
            for category in deletable_categories:
                category.delete()
            
            message = f'{deleted_count} categories have been deleted.'
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid action.'
            })
        
        return JsonResponse({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error performing bulk action. Please try again.'
        })

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_reorder_categories_view(request):
    """Reorder categories by drag and drop"""
    try:
        data = json.loads(request.body)
        category_orders = data.get('category_orders', [])
        
        if not category_orders:
            return JsonResponse({
                'success': False,
                'message': 'No category order data provided.'
            })
        
        updated_count = 0
        for item in category_orders:
            category_id = item.get('id')
            sort_order = item.get('order')
            
            if category_id and sort_order is not None:
                DemoCategory.objects.filter(id=category_id).update(sort_order=sort_order)
                updated_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'{updated_count} categories have been reordered successfully.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error reordering categories. Please try again.'
        })

@login_required
@user_passes_test(is_admin)
def admin_category_stats_view(request):
    """AJAX endpoint for category stats"""
    try:
        stats = {
            'total_categories': DemoCategory.objects.count(),
            'active_categories': DemoCategory.objects.filter(is_active=True).count(),
            'inactive_categories': DemoCategory.objects.filter(is_active=False).count(),
            'categories_with_demos': DemoCategory.objects.filter(demos__isnull=False).distinct().count(),
            'empty_categories': DemoCategory.objects.filter(demos__isnull=True).count(),
            'total_demos': Demo.objects.count(),
            'active_demos': Demo.objects.filter(is_active=True).count(),
        }
        
        return JsonResponse({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error fetching statistics.'
        })

# Additional utility views for better admin experience

@login_required
@user_passes_test(is_admin)
def admin_category_duplicate_view(request, category_id):
    """Duplicate an existing category"""
    if request.method == 'POST':
        try:
            original_category = get_object_or_404(DemoCategory, id=category_id)
            
            # Create duplicate with modified name
            duplicate_name = f"{original_category.name} (Copy)"
            counter = 1
            while DemoCategory.objects.filter(name=duplicate_name).exists():
                duplicate_name = f"{original_category.name} (Copy {counter})"
                counter += 1
            
            duplicate_category = DemoCategory.objects.create(
                name=duplicate_name,
                description=original_category.description,
                icon=original_category.icon,
                sort_order=original_category.sort_order + 1,
                is_active=False  # Create as inactive initially
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Category "{duplicate_category.name}" has been created as a copy.',
                'category_id': duplicate_category.id
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'Error duplicating category. Please try again.'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    })

@login_required
@user_passes_test(is_admin)
def admin_category_export_view(request):
    """Export categories as CSV"""
    import csv
    from django.http import HttpResponse
    from datetime import datetime
    
    response = HttpResponse(content_type='text/csv')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="categories_export_{timestamp}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'ID', 'Name', 'Description', 'Icon', 'Sort Order', 
        'Status', 'Demo Count', 'Created Date', 'Slug'
    ])
    
    # Get categories with demo count
    categories = DemoCategory.objects.annotate(
        demo_count=Count('demos')
    ).order_by('sort_order', 'name')
    
    # Write category data
    for category in categories:
        writer.writerow([
            category.id,
            category.name,
            category.description or '',
            category.icon or '',
            category.sort_order,
            'Active' if category.is_active else 'Inactive',
            category.demo_count,
            category.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            category.slug
        ])
    
    return response