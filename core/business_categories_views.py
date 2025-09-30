# core/views.py - Add these Business Category CRUD views

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.views.decorators.http import require_http_methods
from accounts.models import BusinessCategory, BusinessSubCategory

# Check if user is admin
def is_admin(user):
    return user.is_staff or user.is_superuser

# =====================================
# BUSINESS CATEGORY VIEWS
# =====================================

@login_required
@user_passes_test(is_admin)
def admin_business_categories(request):
    """List all business categories"""
    
    # Search functionality
    search_query = request.GET.get('search', '')
    
    # Filter categories
    categories = BusinessCategory.objects.annotate(
        subcategory_count=Count('subcategories'),
        customer_count=Count('customers')
    ).order_by('sort_order', 'name')
    
    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Stats
    total_categories = BusinessCategory.objects.count()
    active_categories = BusinessCategory.objects.filter(is_active=True).count()
    total_subcategories = BusinessSubCategory.objects.count()
    
    context = {
        'categories': categories,
        'search_query': search_query,
        'total_categories': total_categories,
        'active_categories': active_categories,
        'total_subcategories': total_subcategories,
        'breadcrumbs': [
            {'title': 'Business Categories', 'url': '#'}
        ]
    }
    
    return render(request, 'admin/business_categories/list.html', context)

@login_required
@user_passes_test(is_admin)
def admin_business_category_create(request):
    """Create new business category"""
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        icon = request.POST.get('icon', '')
        is_active = request.POST.get('is_active') == 'on'
        sort_order = request.POST.get('sort_order', 0)
        
        # Validation
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('core:admin_business_category_create')
        
        # Check if category already exists
        if BusinessCategory.objects.filter(name=name).exists():
            messages.error(request, f'Category "{name}" already exists.')
            return redirect('core:admin_business_category_create')
        
        # Create category
        try:
            category = BusinessCategory.objects.create(
                name=name,
                description=description,
                icon=icon,
                is_active=is_active,
                sort_order=int(sort_order)
            )
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect('core:admin_business_categories')
        except Exception as e:
            messages.error(request, f'Error creating category: {str(e)}')
            return redirect('core:admin_business_category_create')
    
    # Get next sort order
    last_category = BusinessCategory.objects.order_by('-sort_order').first()
    next_sort_order = (last_category.sort_order + 1) if last_category else 0
    
    context = {
        'next_sort_order': next_sort_order,
        'breadcrumbs': [
            {'title': 'Business Categories', 'url': '/admin/business-categories/'},
            {'title': 'Create Category', 'url': '#'}
        ]
    }
    
    return render(request, 'admin/business_categories/create.html', context)

@login_required
@user_passes_test(is_admin)
def admin_business_category_edit(request, category_id):
    """Edit business category"""
    
    category = get_object_or_404(BusinessCategory, id=category_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        icon = request.POST.get('icon', '')
        is_active = request.POST.get('is_active') == 'on'
        sort_order = request.POST.get('sort_order', 0)
        
        # Validation
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('core:admin_business_category_edit', category_id=category_id)
        
        # Check if name already exists (excluding current category)
        if BusinessCategory.objects.filter(name=name).exclude(id=category_id).exists():
            messages.error(request, f'Category "{name}" already exists.')
            return redirect('core:admin_business_category_edit', category_id=category_id)
        
        # Update category
        try:
            category.name = name
            category.description = description
            category.icon = icon
            category.is_active = is_active
            category.sort_order = int(sort_order)
            category.save()
            
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('core:admin_business_categories')
        except Exception as e:
            messages.error(request, f'Error updating category: {str(e)}')
            return redirect('core:admin_business_category_edit', category_id=category_id)
    
    context = {
        'category': category,
        'subcategory_count': category.subcategories.count(),
        'customer_count': category.customers.count(),
        'breadcrumbs': [
            {'title': 'Business Categories', 'url': '/admin/business-categories/'},
            {'title': f'Edit: {category.name}', 'url': '#'}
        ]
    }
    
    return render(request, 'admin/business_categories/edit.html', context)

@login_required
@user_passes_test(is_admin)
def admin_business_category_delete(request, category_id):
    """Delete business category"""
    
    category = get_object_or_404(BusinessCategory, id=category_id)
    
    if request.method == 'POST':
        # Check if category has customers
        customer_count = category.customers.count()
        if customer_count > 0:
            messages.error(
                request, 
                f'Cannot delete "{category.name}". It has {customer_count} customer(s) associated with it.'
            )
            return redirect('core:admin_business_categories')
        
        # Delete category (subcategories will be deleted automatically due to CASCADE)
        category_name = category.name
        category.delete()
        
        messages.success(request, f'Category "{category_name}" deleted successfully!')
        return redirect('core:admin_business_categories')
    
    context = {
        'category': category,
        'subcategory_count': category.subcategories.count(),
        'customer_count': category.customers.count(),
        'breadcrumbs': [
            {'title': 'Business Categories', 'url': '/admin/business-categories/'},
            {'title': f'Delete: {category.name}', 'url': '#'}
        ]
    }
    
    return render(request, 'admin/business_categories/delete.html', context)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_business_category_toggle_status(request, category_id):
    """Toggle category active status"""
    
    category = get_object_or_404(BusinessCategory, id=category_id)
    category.is_active = not category.is_active
    category.save()
    
    status = "activated" if category.is_active else "deactivated"
    messages.success(request, f'Category "{category.name}" {status} successfully!')
    
    return redirect('core:admin_business_categories')

# =====================================
# BUSINESS SUBCATEGORY VIEWS
# =====================================

@login_required
@user_passes_test(is_admin)
def admin_business_subcategories(request):
    """List all business subcategories"""
    
    # Get filter parameters
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    
    # Get all categories for filter dropdown
    categories = BusinessCategory.objects.all().order_by('name')
    
    # Filter subcategories
    subcategories = BusinessSubCategory.objects.select_related('category').annotate(
        customer_count=Count('customers')
    ).order_by('category__name', 'sort_order', 'name')
    
    if search_query:
        subcategories = subcategories.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )
    
    if category_filter:
        subcategories = subcategories.filter(category_id=category_filter)
    
    # Stats
    total_subcategories = BusinessSubCategory.objects.count()
    active_subcategories = BusinessSubCategory.objects.filter(is_active=True).count()
    
    context = {
        'subcategories': subcategories,
        'categories': categories,
        'search_query': search_query,
        'category_filter': category_filter,
        'total_subcategories': total_subcategories,
        'active_subcategories': active_subcategories,
        'breadcrumbs': [
            {'title': 'Business Subcategories', 'url': '#'}
        ]
    }
    
    return render(request, 'admin/business_subcategories/list.html', context)

@login_required
@user_passes_test(is_admin)
def admin_business_subcategory_create(request):
    """Create new business subcategory"""
    
    categories = BusinessCategory.objects.filter(is_active=True).order_by('name')
    
    if request.method == 'POST':
        category_id = request.POST.get('category')
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        sort_order = request.POST.get('sort_order', 0)
        
        # Validation
        if not category_id:
            messages.error(request, 'Parent category is required.')
            return redirect('core:admin_business_subcategory_create')
        
        if not name:
            messages.error(request, 'Subcategory name is required.')
            return redirect('core:admin_business_subcategory_create')
        
        category = get_object_or_404(BusinessCategory, id=category_id)
        
        # Check if subcategory already exists in this category
        if BusinessSubCategory.objects.filter(category=category, name=name).exists():
            messages.error(request, f'Subcategory "{name}" already exists in "{category.name}".')
            return redirect('core:admin_business_subcategory_create')
        
        # Create subcategory
        try:
            subcategory = BusinessSubCategory.objects.create(
                category=category,
                name=name,
                description=description,
                is_active=is_active,
                sort_order=int(sort_order)
            )
            messages.success(request, f'Subcategory "{subcategory.name}" created successfully!')
            return redirect('core:admin_business_subcategories')
        except Exception as e:
            messages.error(request, f'Error creating subcategory: {str(e)}')
            return redirect('core:admin_business_subcategory_create')
    
    context = {
        'categories': categories,
        'breadcrumbs': [
            {'title': 'Business Subcategories', 'url': '/admin/business-subcategories/'},
            {'title': 'Create Subcategory', 'url': '#'}
        ]
    }
    
    return render(request, 'admin/business_subcategories/create.html', context)

@login_required
@user_passes_test(is_admin)
def admin_business_subcategory_edit(request, subcategory_id):
    """Edit business subcategory"""
    
    subcategory = get_object_or_404(BusinessSubCategory, id=subcategory_id)
    categories = BusinessCategory.objects.filter(is_active=True).order_by('name')
    
    if request.method == 'POST':
        category_id = request.POST.get('category')
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        sort_order = request.POST.get('sort_order', 0)
        
        # Validation
        if not category_id:
            messages.error(request, 'Parent category is required.')
            return redirect('core:admin_business_subcategory_edit', subcategory_id=subcategory_id)
        
        if not name:
            messages.error(request, 'Subcategory name is required.')
            return redirect('core:admin_business_subcategory_edit', subcategory_id=subcategory_id)
        
        category = get_object_or_404(BusinessCategory, id=category_id)
        
        # Check if name already exists in this category (excluding current subcategory)
        if BusinessSubCategory.objects.filter(
            category=category, 
            name=name
        ).exclude(id=subcategory_id).exists():
            messages.error(request, f'Subcategory "{name}" already exists in "{category.name}".')
            return redirect('core:admin_business_subcategory_edit', subcategory_id=subcategory_id)
        
        # Update subcategory
        try:
            subcategory.category = category
            subcategory.name = name
            subcategory.description = description
            subcategory.is_active = is_active
            subcategory.sort_order = int(sort_order)
            subcategory.save()
            
            messages.success(request, f'Subcategory "{subcategory.name}" updated successfully!')
            return redirect('core:admin_business_subcategories')
        except Exception as e:
            messages.error(request, f'Error updating subcategory: {str(e)}')
            return redirect('core:admin_business_subcategory_edit', subcategory_id=subcategory_id)
    
    context = {
        'subcategory': subcategory,
        'categories': categories,
        'customer_count': subcategory.customers.count(),
        'breadcrumbs': [
            {'title': 'Business Subcategories', 'url': '/admin/business-subcategories/'},
            {'title': f'Edit: {subcategory.name}', 'url': '#'}
        ]
    }
    
    return render(request, 'admin/business_subcategories/edit.html', context)

@login_required
@user_passes_test(is_admin)
def admin_business_subcategory_delete(request, subcategory_id):
    """Delete business subcategory"""
    
    subcategory = get_object_or_404(BusinessSubCategory, id=subcategory_id)
    
    if request.method == 'POST':
        # Check if subcategory has customers
        customer_count = subcategory.customers.count()
        if customer_count > 0:
            messages.error(
                request, 
                f'Cannot delete "{subcategory.name}". It has {customer_count} customer(s) associated with it.'
            )
            return redirect('core:admin_business_subcategories')
        
        # Delete subcategory
        subcategory_name = subcategory.name
        subcategory.delete()
        
        messages.success(request, f'Subcategory "{subcategory_name}" deleted successfully!')
        return redirect('core:admin_business_subcategories')
    
    context = {
        'subcategory': subcategory,
        'customer_count': subcategory.customers.count(),
        'breadcrumbs': [
            {'title': 'Business Subcategories', 'url': '/admin/business-subcategories/'},
            {'title': f'Delete: {subcategory.name}', 'url': '#'}
        ]
    }
    
    return render(request, 'admin/business_subcategories/delete.html', context)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_business_subcategory_toggle_status(request, subcategory_id):
    """Toggle subcategory active status"""
    
    subcategory = get_object_or_404(BusinessSubCategory, id=subcategory_id)
    subcategory.is_active = not subcategory.is_active
    subcategory.save()
    
    status = "activated" if subcategory.is_active else "deactivated"
    messages.success(request, f'Subcategory "{subcategory.name}" {status} successfully!')
    
    return redirect('core:admin_business_subcategories')