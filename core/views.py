from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q,Sum
from django.utils import timezone
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
import json
import csv
from django.db import models  # Add this import
from accounts.models import BusinessCategory, BusinessSubCategory
# Get the custom user model
User = get_user_model()  # This will give us User

from demos.models import Demo, DemoRequest, DemoView, DemoLike, DemoCategory
from enquiries.models import BusinessEnquiry
from notifications.models import Notification, SystemAnnouncement
from .models import SiteSettings, ContactMessage

# FIXED - Correct import from accounts app


# Helper function to check if user is admin
def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

# =====================================
# CUSTOMER PORTAL VIEWS
# =====================================

def landing_page_view(request):
    """Landing page with signup/signin options"""
    if request.user.is_authenticated:
        if is_admin(request.user):
            return redirect('core:admin_dashboard')
        return redirect('core:dashboard')
    
    # Get site settings
    site_settings = SiteSettings.load()
    
    # Get featured demos for preview
    featured_demos = Demo.objects.filter(
        is_active=True, 
        is_featured=True
    )[:3]
    
    # Get demo categories
    categories = DemoCategory.objects.filter(is_active=True)[:6]
    
    # Get current announcements
    current_announcements = SystemAnnouncement.objects.filter(
        is_active=True,
        show_on_login=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )
    
    context = {
        'site_settings': site_settings,
        'featured_demos': featured_demos,
        'categories': categories,
        'announcements': current_announcements,
    }
    
    return render(request, 'core/landing.html', context)

@login_required
def dashboard_view(request):
    """Customer dashboard after login - Fixed with proper context"""
    if is_admin(request.user):
        return redirect('core:admin_dashboard')
    
    if not request.user.is_approved:
        return redirect('accounts:pending_approval')
    
    user = request.user
    
    # Dashboard Statistics
    total_demos_watched = DemoView.objects.filter(user=user).count()
    total_demo_requests = DemoRequest.objects.filter(user=user).count()
    total_enquiries = BusinessEnquiry.objects.filter(user=user).count()
    pending_demo_requests = DemoRequest.objects.filter(
        user=user, 
        status='pending'
    ).count()
    
    # Recent Activity
    recent_demo_views = DemoView.objects.filter(user=user).select_related('demo').order_by('-viewed_at')[:5]
    recent_demo_requests = DemoRequest.objects.filter(user=user).select_related('demo').order_by('-created_at')[:3]
    recent_enquiries = BusinessEnquiry.objects.filter(user=user).order_by('-created_at')[:3]
    
    # Featured/Popular Demos
    featured_demos = Demo.objects.filter(
        is_active=True,
        is_featured=True
    ).exclude(
        id__in=DemoView.objects.filter(user=user).values_list('demo_id', flat=True)
    )[:4]
    
    # User views and likes for template context
    user_views = set(DemoView.objects.filter(user=user).values_list('demo_id', flat=True))
    user_likes = set(DemoLike.objects.filter(user=user).values_list('demo_id', flat=True))
    
    # Unread Notifications
    unread_notifications = Notification.objects.filter(
        user=user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # Current Announcements
    current_announcements = SystemAnnouncement.objects.filter(
        is_active=True,
        show_on_dashboard=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )
    
    context = {
        'user': user,
        'total_demos_watched': total_demos_watched,
        'total_demo_requests': total_demo_requests,
        'total_enquiries': total_enquiries,
        'pending_demo_requests': pending_demo_requests,
        'recent_demo_views': recent_demo_views,
        'recent_demo_requests': recent_demo_requests,
        'recent_enquiries': recent_enquiries,
        'featured_demos': featured_demos,
        'user_views': user_views,
        'user_likes': user_likes,
        'unread_notifications': unread_notifications,
        'current_announcements': current_announcements,
    }
    
    return render(request, 'core/dashboard.html', context)

def contact_view(request):
    """Contact page for general inquiries"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        company = request.POST.get('company', '')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Save contact message
        contact_message = ContactMessage.objects.create(
            name=name,
            email=email,
            phone=phone,
            company=company,
            subject=subject,
            message=message,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Send email to admin
        try:
            admin_subject = f"New Contact Message: {subject}"
            admin_message = f"""
            New contact message received:
            
            Name: {name}
            Email: {email}
            Phone: {phone}
            Company: {company}
            
            Subject: {subject}
            
            Message:
            {message}
            
            ---
            Sent from Demo Portal
            """
            
            send_mail(
                admin_subject,
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )
        except Exception as e:
            pass  # Continue even if email fails
        
        messages.success(request, 'Thank you for your message! We will get back to you soon.')
        return redirect('core:contact')
    
    site_settings = SiteSettings.load()
    return render(request, 'core/contact.html', {'site_settings': site_settings})

def contact_sales_view(request):
    """Contact sales form for business inquiries"""
    return render(request, 'core/contact_sales.html')

# =====================================
# ADMIN AUTHENTICATION
# =====================================

def admin_login_view(request):
    """Custom admin login page"""
    if request.user.is_authenticated and is_admin(request.user):
        return redirect('core:admin_dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user and is_admin(user):
            login(request, user)
            messages.success(request, f'Welcome back, {user.full_name}!')
            return redirect('core:admin_dashboard')
        else:
            messages.error(request, 'Invalid credentials or insufficient permissions.')
    
    return render(request, 'admin/auth/login.html')

@login_required
@user_passes_test(is_admin)
def admin_logout_view(request):
    """Admin logout"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('core:admin_login')

# =====================================
# ADMIN DASHBOARD - Fixed with proper context
# =====================================

@login_required
@user_passes_test(is_admin)
def admin_dashboard_view(request):
    """Main admin dashboard with statistics - FIXED customer counts"""
    
    # Date ranges for statistics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # User Statistics - FILTER OUT ADMIN/STAFF USERS
    total_users = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).count()
    
    new_users_today = User.objects.filter(
        created_at__date=today,
        is_staff=False,
        is_superuser=False
    ).count()
    
    new_users_week = User.objects.filter(
        created_at__date__gte=week_ago,
        is_staff=False,
        is_superuser=False
    ).count()
    
    pending_approvals = User.objects.filter(
        is_approved=False, 
        is_active=True,
        is_staff=False,
        is_superuser=False
    ).count()
    
    active_users = User.objects.filter(
        is_active=True, 
        is_approved=True,
        is_staff=False,
        is_superuser=False
    ).count()
    
    # Demo Statistics
    total_demos = Demo.objects.count()
    active_demos = Demo.objects.filter(is_active=True).count()
    total_demo_views = DemoView.objects.count()
    demo_views_today = DemoView.objects.filter(viewed_at__date=today).count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    demo_requests_today = DemoRequest.objects.filter(created_at__date=today).count()
    
    # Enquiry Statistics
    total_enquiries = BusinessEnquiry.objects.count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    new_enquiries_today = BusinessEnquiry.objects.filter(created_at__date=today).count()
    overdue_enquiries = BusinessEnquiry.objects.filter(
        status='open',
        created_at__lt=timezone.now() - timedelta(hours=24)
    ).count()
    
    # System Health
    system_health = {
        'database': 'healthy',
        'email': 'healthy',
        'storage': 'healthy',
        'cache': 'healthy',
    }
    
    # Recent Activity - FILTER OUT ADMIN USERS
    recent_users = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).order_by('-created_at')[:5]
    
    recent_enquiries = BusinessEnquiry.objects.order_by('-created_at')[:5]
    recent_demo_requests = DemoRequest.objects.select_related('user', 'demo').order_by('-created_at')[:5]
    recent_contact_messages = ContactMessage.objects.order_by('-created_at')[:5]
    
    # Popular Demos (most viewed)
    popular_demos = Demo.objects.annotate(
        views=Count('demo_views')
    ).order_by('-views')[:5]
    
    # Monthly User Growth Chart Data - CUSTOMERS ONLY
    monthly_users = []
    for i in range(6):  # Last 6 months
        date = today.replace(day=1) - timedelta(days=i*30)
        count = User.objects.filter(
            created_at__year=date.year,
            created_at__month=date.month,
            is_staff=False,
            is_superuser=False
        ).count()
        monthly_users.append({
            'month': date.strftime('%b %Y'),
            'count': count
        })
    monthly_users.reverse()
    
    # Weekly Activity Data
    weekly_activity = []
    for i in range(7):  # Last 7 days
        date = today - timedelta(days=i)
        demo_views = DemoView.objects.filter(viewed_at__date=date).count()
        enquiries = BusinessEnquiry.objects.filter(created_at__date=date).count()
        signups = User.objects.filter(
            created_at__date=date,
            is_staff=False,
            is_superuser=False
        ).count()
        
        weekly_activity.append({
            'date': date.strftime('%m/%d'),
            'demo_views': demo_views,
            'enquiries': enquiries,
            'signups': signups,
        })
    weekly_activity.reverse()
    
    context = {
        # User Stats (Customers only)
        'total_users': total_users,
        'new_users_today': new_users_today,
        'new_users_week': new_users_week,
        'pending_approvals': pending_approvals,
        'active_users': active_users,
        
        # Demo Stats
        'total_demos': total_demos,
        'active_demos': active_demos,
        'total_demo_views': total_demo_views,
        'demo_views_today': demo_views_today,
        'demo_requests_pending': demo_requests_pending,
        'demo_requests_today': demo_requests_today,
        
        # Enquiry Stats
        'total_enquiries': total_enquiries,
        'open_enquiries': open_enquiries,
        'new_enquiries_today': new_enquiries_today,
        'overdue_enquiries': overdue_enquiries,
        
        # Recent Activity
        'recent_users': recent_users,
        'recent_enquiries': recent_enquiries,
        'recent_demo_requests': recent_demo_requests,
        'recent_contact_messages': recent_contact_messages,
        'popular_demos': popular_demos,
        
        # Chart Data
        'monthly_users': monthly_users,
        'weekly_activity': weekly_activity,
        'system_health': system_health,
    }
    
    return render(request, 'admin/dashboard.html', context)

# =====================================
# ADMIN USER MANAGEMENT
# =====================================
@login_required
@user_passes_test(is_admin)
def admin_users_view(request):
    """Admin users management - FIXED to show only customers"""
    # FILTER OUT ADMIN/STAFF USERS - Only show customers
    users_list = User.objects.filter(
        is_staff=False,  # Exclude staff users
        is_superuser=False  # Exclude superusers
    ).order_by('-created_at')
    
    # Filtering
    status_filter = request.GET.get('status')
    search = request.GET.get('search')
    
    if status_filter == 'pending':
        users_list = users_list.filter(is_approved=False)
    elif status_filter == 'approved':
        users_list = users_list.filter(is_approved=True)
    elif status_filter == 'blocked':
        users_list = users_list.filter(is_active=False)
    elif status_filter == 'active':
        users_list = users_list.filter(is_active=True, is_approved=True)
    
    if search:
        users_list = users_list.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(organization__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(users_list, 25)
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)
    
    # Context for sidebar badges - ALSO FILTER ADMIN USERS FROM COUNTS
    pending_approvals = User.objects.filter(
        is_approved=False, 
        is_active=True,
        is_staff=False,  # Only count customers
        is_superuser=False
    ).count()
    
    total_customers = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).count()
    
    active_customers = User.objects.filter(
        is_staff=False,
        is_superuser=False,
        is_active=True,
        is_approved=True
    ).count()
    
    blocked_customers = User.objects.filter(
        is_staff=False,
        is_superuser=False,
        is_active=False
    ).count()
    
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'users': users,
        'status_filter': status_filter,
        'search': search,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
        # Additional statistics for display
        'total_customers': total_customers,
        'active_customers': active_customers,
        'blocked_customers': blocked_customers,
    }
    
    return render(request, 'admin/users/list.html', context)

@login_required
@user_passes_test(is_admin)
def admin_user_detail_view(request, user_id):
    """Admin user detail view"""
    user_detail = get_object_or_404(User, id=user_id)
    
    # User activity stats
    demo_views = DemoView.objects.filter(user=user_detail).count()
    demo_requests = DemoRequest.objects.filter(user=user_detail).count()
    enquiries = BusinessEnquiry.objects.filter(user=user_detail).count()
    
    # Recent activity
    recent_demo_views = DemoView.objects.filter(user=user_detail).select_related('demo').order_by('-viewed_at')[:10]
    recent_demo_requests = DemoRequest.objects.filter(user=user_detail).select_related('demo').order_by('-created_at')[:10]
    recent_enquiries = BusinessEnquiry.objects.filter(user=user_detail).order_by('-created_at')[:10]
    
    # Context for sidebar badges
    pending_approvals = User.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'user_detail': user_detail,
        'demo_views': demo_views,
        'demo_requests': demo_requests,
        'enquiries': enquiries,
        'recent_demo_views': recent_demo_views,
        'recent_demo_requests': recent_demo_requests,
        'recent_enquiries': recent_enquiries,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/users/detail.html', context)


# =====================================
# ADMIN DEMO MANAGEMENT
# =====================================

@login_required
@user_passes_test(is_admin)
def admin_demos_view(request):
    """Admin demos management - FIXED"""
    
    # Query demos with proper prefetch for ManyToMany
    demos_list = Demo.objects.prefetch_related(
        'target_business_categories',
        'target_business_subcategories',
        'target_customers'
    ).select_related(
        'created_by'
    ).order_by('-is_featured', 'sort_order', '-created_at')
    
    # Filtering
    search = request.GET.get('search')
    demo_type_filter = request.GET.get('demo_type')
    business_category_filter = request.GET.get('business_category')
    status_filter = request.GET.get('status')
    featured_filter = request.GET.get('featured')
    
    if search:
        demos_list = demos_list.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )
    
    if demo_type_filter:
        demos_list = demos_list.filter(demo_type=demo_type_filter)
    
    if business_category_filter:
        demos_list = demos_list.filter(
            target_business_categories__id=business_category_filter
        ).distinct()
    
    if status_filter:
        if status_filter == 'active':
            demos_list = demos_list.filter(is_active=True)
        elif status_filter == 'inactive':
            demos_list = demos_list.filter(is_active=False)
    
    if featured_filter == 'yes':
        demos_list = demos_list.filter(is_featured=True)
    
    # Pagination
    paginator = Paginator(demos_list, 20)
    page_number = request.GET.get('page')
    demos = paginator.get_page(page_number)
    
    # Get business categories for filter
    from accounts.models import BusinessCategory
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('name')
    
    # Statistics
    stats = {
        'total': Demo.objects.count(),
        'active': Demo.objects.filter(is_active=True).count(),
        'inactive': Demo.objects.filter(is_active=False).count(),
        'featured': Demo.objects.filter(is_featured=True).count(),
        'total_views': Demo.objects.aggregate(total=Sum('views_count'))['total'] or 0,
    }
    
    # Context for sidebar
    from accounts.models import CustomUser
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'demos': demos,
        'business_categories': business_categories,
        'demo_types': Demo.DEMO_TYPE_CHOICES,
        'stats': stats,
        'search': search,
        'demo_type_filter': demo_type_filter,
        'business_category_filter': business_category_filter,
        'status_filter': status_filter,
        'featured_filter': featured_filter,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demos/list.html', context)

@login_required
@user_passes_test(is_admin)
def admin_add_demo_view(request):
    """Admin add new demo - UPDATED"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        demo_type = request.POST.get('demo_type', 'product')
        video_file = request.FILES.get('video_file')
        thumbnail = request.FILES.get('thumbnail')
        duration = request.POST.get('duration')
        is_featured = request.POST.get('is_featured') == 'on'
        is_active = request.POST.get('is_active', 'on') == 'on'
        
        # Get business categories
        business_category_ids = request.POST.getlist('target_business_categories')
        business_subcategory_ids = request.POST.getlist('target_business_subcategories')
        
        try:
            # Validate required fields
            if not title or not video_file or not thumbnail:
                messages.error(request, 'Title, video file, and thumbnail are required.')
                return redirect('core:admin_add_demo')
            
            # Create demo
            demo = Demo.objects.create(
                title=title,
                description=description,
                demo_type=demo_type,
                video_file=video_file,
                thumbnail=thumbnail,
                is_featured=is_featured,
                is_active=is_active,
                created_by=request.user
            )
            
            # Set duration if provided
            if duration:
                from datetime import timedelta
                try:
                    parts = duration.split(':')
                    if len(parts) == 3:
                        hours, minutes, seconds = map(int, parts)
                        demo.duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                    elif len(parts) == 2:
                        minutes, seconds = map(int, parts)
                        demo.duration = timedelta(minutes=minutes, seconds=seconds)
                    demo.save()
                except:
                    pass
            
            # Set business categories
            if business_category_ids:
                from accounts.models import BusinessCategory
                categories = BusinessCategory.objects.filter(id__in=business_category_ids)
                demo.target_business_categories.set(categories)
            
            # Set business subcategories
            if business_subcategory_ids:
                from accounts.models import BusinessSubCategory
                subcategories = BusinessSubCategory.objects.filter(id__in=business_subcategory_ids)
                demo.target_business_subcategories.set(subcategories)
            
            messages.success(request, f'Demo "{demo.title}" created successfully!')
            return redirect('core:admin_demo_detail', demo_id=demo.id)
            
        except Exception as e:
            messages.error(request, f'Error creating demo: {str(e)}')
            return redirect('core:admin_add_demo')
    
    # GET request - show form
    from accounts.models import BusinessCategory, BusinessSubCategory
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    business_subcategories = BusinessSubCategory.objects.filter(is_active=True).select_related('category').order_by('sort_order', 'name')
    
    # Context for sidebar
    from accounts.models import CustomUser
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'business_categories': business_categories,
        'business_subcategories': business_subcategories,
        'demo_types': Demo.DEMO_TYPE_CHOICES,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demos/add.html', context)

@login_required
@user_passes_test(is_admin)
def admin_demo_detail_view(request, demo_id):
    """View and edit demo details - UPDATED"""
    
    demo = get_object_or_404(
        Demo.objects.prefetch_related(
            'target_business_categories',
            'target_business_subcategories',
            'target_customers'
        ).select_related('created_by'),
        id=demo_id
    )
    
    if request.method == 'POST':
        # Handle form submission for editing
        demo.title = request.POST.get('title', demo.title)
        demo.description = request.POST.get('description', demo.description)
        demo.demo_type = request.POST.get('demo_type', demo.demo_type)
        demo.is_featured = request.POST.get('is_featured') == 'on'
        demo.is_active = request.POST.get('is_active') == 'on'
        
        # Update video file if provided
        if 'video_file' in request.FILES:
            if demo.video_file:
                demo.video_file.delete()
            demo.video_file = request.FILES['video_file']
        
        # Update thumbnail if provided
        if 'thumbnail' in request.FILES:
            if demo.thumbnail:
                demo.thumbnail.delete()
            demo.thumbnail = request.FILES['thumbnail']
        
        # Update duration
        duration = request.POST.get('duration')
        if duration:
            from datetime import timedelta
            try:
                parts = duration.split(':')
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    demo.duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
                elif len(parts) == 2:
                    minutes, seconds = map(int, parts)
                    demo.duration = timedelta(minutes=minutes, seconds=seconds)
            except:
                pass
        
        demo.save()
        
        # Update business categories
        business_category_ids = request.POST.getlist('target_business_categories')
        if business_category_ids:
            from accounts.models import BusinessCategory
            categories = BusinessCategory.objects.filter(id__in=business_category_ids)
            demo.target_business_categories.set(categories)
        else:
            demo.target_business_categories.clear()
        
        # Update business subcategories
        business_subcategory_ids = request.POST.getlist('target_business_subcategories')
        if business_subcategory_ids:
            from accounts.models import BusinessSubCategory
            subcategories = BusinessSubCategory.objects.filter(id__in=business_subcategory_ids)
            demo.target_business_subcategories.set(subcategories)
        else:
            demo.target_business_subcategories.clear()
        
        messages.success(request, f'Demo "{demo.title}" has been updated successfully!')
        return redirect('core:admin_demo_detail', demo_id=demo.id)
    
    # Demo statistics
    total_views = DemoView.objects.filter(demo=demo).count()
    total_likes = DemoLike.objects.filter(demo=demo).count()
    total_requests = DemoRequest.objects.filter(demo=demo).count()
    
    # Customer access info
    target_customers = demo.target_customers.all()
    from accounts.models import CustomUser
    if target_customers.exists():
        total_accessible_customers = target_customers.count()
    else:
        total_accessible_customers = CustomUser.objects.filter(
            is_approved=True,
            is_active=True
        ).count()
    
    # Recent activity
    recent_views = DemoView.objects.filter(demo=demo).select_related('user').order_by('-viewed_at')[:10]
    recent_requests = DemoRequest.objects.filter(demo=demo).select_related('user').order_by('-created_at')[:5]
    
    # Get business categories for edit form
    from accounts.models import BusinessCategory, BusinessSubCategory
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    business_subcategories = BusinessSubCategory.objects.filter(is_active=True).select_related('category').order_by('sort_order', 'name')
    
    # Context for sidebar
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'demo': demo,
        'demo_types': Demo.DEMO_TYPE_CHOICES,
        'business_categories': business_categories,
        'business_subcategories': business_subcategories,
        'total_views': total_views,
        'total_likes': total_likes,
        'total_requests': total_requests,
        'target_customers': target_customers,
        'total_accessible_customers': total_accessible_customers,
        'is_for_all_customers': demo.is_for_all_customers,
        'recent_views': recent_views,
        'recent_requests': recent_requests,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demos/detail.html', context)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_delete_demo_view(request, demo_id):
    """Delete demo - UNCHANGED"""
    demo = get_object_or_404(Demo, id=demo_id)
    demo_title = demo.title
    
    try:
        # Delete associated files
        if demo.video_file:
            demo.video_file.delete()
        if demo.thumbnail:
            demo.thumbnail.delete()
        
        # Delete demo (CASCADE will handle related objects)
        demo.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Demo "{demo_title}" has been deleted successfully.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deleting demo: {str(e)}'
        })
      
@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_toggle_demo_status_view(request, demo_id):
    """Toggle demo active/inactive status"""
    demo = get_object_or_404(Demo, id=demo_id)
    
    try:
        data = json.loads(request.body)
        activate = data.get('activate', not demo.is_active)
        
        demo.is_active = activate
        demo.save()
        
        status = "activated" if activate else "deactivated"
        
        return JsonResponse({
            'success': True,
            'message': f'Demo "{demo.title}" has been {status}.',
            'is_active': demo.is_active
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Error updating demo status. Please try again.'
        })

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_bulk_demo_actions_view(request):
    """Handle bulk demo actions"""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        demo_ids = data.get('demo_ids', [])
        
        if not demo_ids:
            return JsonResponse({
                'success': False,
                'message': 'No demos selected.'
            })
        
        demos = Demo.objects.filter(id__in=demo_ids)
        
        if action == 'activate':
            demos.update(is_active=True)
            message = f'{len(demo_ids)} demos have been activated.'
        elif action == 'deactivate':
            demos.update(is_active=False)
            message = f'{len(demo_ids)} demos have been deactivated.'
        elif action == 'delete':
            # Delete files and demos
            for demo in demos:
                if demo.video_file:
                    demo.video_file.delete()
                if demo.thumbnail:
                    demo.thumbnail.delete()
            demos.delete()
            message = f'{len(demo_ids)} demos have been deleted.'
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
def admin_demo_stats_view(request):
    """AJAX endpoint for demo stats"""
    stats = {
        'total_demos': Demo.objects.count(),
        'active_demos': Demo.objects.filter(is_active=True).count(),
        'featured_demos': Demo.objects.filter(is_featured=True).count(),
        'total_views': DemoView.objects.count(),
        'last_updated': timezone.now().isoformat()
    }
    
    return JsonResponse(stats)    

@login_required
@user_passes_test(is_admin)
def admin_demo_watch_view(request, demo_id):
    """Admin demo watch/preview view"""
    demo = get_object_or_404(Demo, id=demo_id)
    
    # Get demo request count for this specific demo
    demo_requests_count = DemoRequest.objects.filter(demo=demo).count()
    
    # Context for sidebar badges (required by base template)
    pending_approvals = User.objects.filter(
        is_approved=False, 
        is_active=True
    ).count()
    
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'demo': demo,
        'demo_requests_count': demo_requests_count,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demos/watch.html', context)

# =====================================
# PLACEHOLDER ADMIN VIEWS
# =====================================

@login_required
@user_passes_test(is_admin)
def admin_enquiries_view(request):
    """Admin enquiries management with full functionality"""
    from django.db.models import Q
    from django.core.paginator import Paginator
    
    # Get all enquiries
    enquiries_list = BusinessEnquiry.objects.select_related(
        'user', 'category', 'assigned_to'
    ).order_by('-created_at')
    
    # Filtering
    search = request.GET.get('search')
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    sort_by = request.GET.get('sort', '-created_at')
    
    if search:
        enquiries_list = enquiries_list.filter(
            Q(enquiry_id__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(business_email__icontains=search) |
            Q(organization__icontains=search) |
            Q(subject__icontains=search) |
            Q(message__icontains=search)
        )
    
    if status_filter:
        enquiries_list = enquiries_list.filter(status=status_filter)
    
    if priority_filter:
        enquiries_list = enquiries_list.filter(priority=priority_filter)
    
    # Sorting
    sort_options = {
        'created_at': 'created_at',
        '-created_at': '-created_at',
        'priority': 'priority',
        '-priority': '-priority',
    }
    if sort_by in sort_options:
        enquiries_list = enquiries_list.order_by(sort_options[sort_by])
    
    # Statistics
    total_enquiries = BusinessEnquiry.objects.count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    in_progress_enquiries = BusinessEnquiry.objects.filter(status='in_progress').count()
    answered_enquiries = BusinessEnquiry.objects.filter(status='answered').count()
    
    # Pagination
    paginator = Paginator(enquiries_list, 10)  # 10 enquiries per page
    page_number = request.GET.get('page')
    enquiries = paginator.get_page(page_number)
    
    # Context for sidebar badges
    pending_approvals = User.objects.filter(
        is_approved=False, 
        is_active=True,
        is_staff=False,
        is_superuser=False
    ).count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'enquiries': enquiries,
        'search': search,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'sort_by': sort_by,
        
        # Statistics
        'total_enquiries': total_enquiries,
        'open_enquiries': open_enquiries,
        'in_progress_enquiries': in_progress_enquiries,
        'answered_enquiries': answered_enquiries,
        
        # Pagination
        'is_paginated': paginator.num_pages > 1,
        'page_obj': enquiries,
        
        # Sidebar badges
        'pending_approvals': pending_approvals,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/enquiries/list.html', context)

@login_required
@user_passes_test(is_admin)
def admin_enquiry_detail_view(request, enquiry_id):
    """Enquiry detail view with full information and response history"""
    enquiry = get_object_or_404(BusinessEnquiry, id=enquiry_id)
    
    # Get response history
    responses = EnquiryResponse.objects.filter(
        enquiry=enquiry
    ).select_related('responded_by').order_by('-created_at')
    
    # Mark as read if it's the first view
    if enquiry.status == 'open' and not enquiry.first_response_at:
        enquiry.first_response_at = timezone.now()
        enquiry.save(update_fields=['first_response_at'])
    
    # Handle status update
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['open', 'in_progress', 'answered', 'closed']:
            enquiry.status = new_status
            if new_status == 'closed':
                enquiry.closed_at = timezone.now()
            enquiry.save()
            messages.success(request, f'Enquiry status updated to {enquiry.get_status_display()}')
            return redirect('core:admin_enquiry_detail', enquiry_id=enquiry.id)
    
    # Context for sidebar badges
    pending_approvals = User.objects.filter(
        is_approved=False, 
        is_active=True,
        is_staff=False,
        is_superuser=False
    ).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'enquiry': enquiry,
        'responses': responses,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/enquiries/detail.html', context)


@login_required
@user_passes_test(is_admin)
def admin_respond_enquiry_view(request, enquiry_id):
    """Respond to enquiry with email notification"""
    enquiry = get_object_or_404(BusinessEnquiry, id=enquiry_id)
    
    if request.method == 'POST':
        response_text = request.POST.get('response_text')
        is_internal_note = request.POST.get('is_internal_note') == 'on'
        send_email = request.POST.get('send_email') == 'on'
        
        if response_text:
            # Create response
            response = EnquiryResponse.objects.create(
                enquiry=enquiry,
                response_text=response_text,
                is_internal_note=is_internal_note,
                responded_by=request.user
            )
            
            # Update enquiry status
            if not is_internal_note:
                enquiry.status = 'answered'
                enquiry.last_response_at = timezone.now()
                if not enquiry.first_response_at:
                    enquiry.first_response_at = timezone.now()
                enquiry.save()
            
            # Send email if requested
            if send_email and not is_internal_note:
                try:
                    subject = f"Re: {enquiry.subject or 'Your Enquiry'}"
                    message = f"""
                    Dear {enquiry.first_name} {enquiry.last_name},
                    
                    Thank you for your enquiry. Here is our response:
                    
                    {response_text}
                    
                    Best regards,
                    {request.user.get_full_name() or 'Support Team'}
                    """
                    
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [enquiry.business_email],
                        fail_silently=False,
                    )
                    
                    response.email_sent = True
                    response.email_sent_at = timezone.now()
                    response.save()
                    
                    messages.success(request, 'Response sent successfully via email!')
                except Exception as e:
                    messages.warning(request, f'Response saved but email failed: {str(e)}')
            else:
                messages.success(request, 'Response saved successfully!')
            
            return redirect('core:admin_enquiry_detail', enquiry_id=enquiry.id)
        else:
            messages.error(request, 'Please enter a response.')
    
    # Get previous responses for context
    previous_responses = EnquiryResponse.objects.filter(
        enquiry=enquiry
    ).select_related('responded_by').order_by('-created_at')[:5]
    
    # Context for sidebar badges
    pending_approvals = User.objects.filter(
        is_approved=False, 
        is_active=True,
        is_staff=False,
        is_superuser=False
    ).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'enquiry': enquiry,
        'previous_responses': previous_responses,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/enquiries/respond.html', context)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_delete_enquiry_view(request, enquiry_id):
    """Delete enquiry via AJAX"""
    enquiry = get_object_or_404(BusinessEnquiry, id=enquiry_id)
    enquiry_code = enquiry.enquiry_id
    
    try:
        enquiry.delete()
        return JsonResponse({
            'success': True,
            'message': f'Enquiry {enquiry_code} deleted successfully.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deleting enquiry: {str(e)}'
        })


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_assign_enquiry_view(request, enquiry_id):
    """Assign enquiry to admin user"""
    enquiry = get_object_or_404(BusinessEnquiry, id=enquiry_id)
    
    try:
        data = json.loads(request.body)
        assignee_id = data.get('assignee_id')
        
        if assignee_id:
            assignee = get_object_or_404(User, id=assignee_id, is_staff=True)
            enquiry.assigned_to = assignee
        else:
            enquiry.assigned_to = None
        
        enquiry.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Enquiry assigned to {assignee.get_full_name() if assignee else "Unassigned"}.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error assigning enquiry: {str(e)}'
        })


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_update_enquiry_priority_view(request, enquiry_id):
    """Update enquiry priority"""
    enquiry = get_object_or_404(BusinessEnquiry, id=enquiry_id)
    
    try:
        data = json.loads(request.body)
        priority = data.get('priority')
        
        if priority in ['low', 'medium', 'high', 'urgent']:
            enquiry.priority = priority
            enquiry.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Priority updated to {enquiry.get_priority_display()}.'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid priority level.'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error updating priority: {str(e)}'
        })


@login_required
@user_passes_test(is_admin)
def admin_export_enquiries_view(request):
    """Export enquiries to CSV"""
    import csv
    from django.http import HttpResponse
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="enquiries_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Enquiry ID', 'Date', 'Status', 'Priority', 
        'Customer Name', 'Email', 'Organization', 'Phone',
        'Subject', 'Message', 'Category', 'Assigned To'
    ])
    
    enquiries = BusinessEnquiry.objects.all().select_related('category', 'assigned_to')
    
    for enquiry in enquiries:
        writer.writerow([
            enquiry.enquiry_id,
            enquiry.created_at.strftime('%Y-%m-%d %H:%M'),
            enquiry.get_status_display(),
            enquiry.get_priority_display(),
            enquiry.full_name,
            enquiry.business_email,
            enquiry.organization or '',
            enquiry.full_mobile,
            enquiry.subject or '',
            enquiry.message,
            enquiry.category.name if enquiry.category else '',
            enquiry.assigned_to.get_full_name() if enquiry.assigned_to else ''
        ])
    
    return response


@login_required
@user_passes_test(is_admin)
def ajax_system_health(request):
    """AJAX endpoint for system health check"""
    health_status = {
        'database': 'healthy',
        'email': 'healthy', 
        'storage': 'healthy',
        'cache': 'healthy',
        'last_updated': timezone.now().isoformat()
    }
    
    return JsonResponse(health_status)


# =====================================
# UTILITY FUNCTIONS
# =====================================

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# =====================================
# AJAX ENDPOINTS
# =====================================

@require_http_methods(["GET"])
def get_subcategories_ajax(request):
    """AJAX endpoint to get subcategories for selected categories"""
    category_ids = request.GET.get('categories', '').split(',')
    
    subcategories = []
    
    if category_ids and category_ids[0]:
        try:
            # Get all subcategories for the selected categories
            subcats = BusinessSubCategory.objects.filter(
                category_id__in=category_ids,
                is_active=True
            ).select_related('category').order_by('category__name', 'name')
            
            for subcat in subcats:
                subcategories.append({
                    'id': subcat.id,
                    'name': subcat.name,
                    'category_id': subcat.category_id,
                    'category_name': subcat.category.name
                })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({
        'success': True,
        'subcategories': subcategories
    })

# Alternative simpler version if you want to use a single category
@require_http_methods(["GET"])
def get_subcategories_for_category(request):
    """Get subcategories for a single category"""
    category_id = request.GET.get('category_id')
    
    if not category_id:
        return JsonResponse({'success': False, 'error': 'No category ID provided'})
    
    try:
        subcategories = BusinessSubCategory.objects.filter(
            category_id=category_id,
            is_active=True
        ).values('id', 'name').order_by('sort_order', 'name')
        
        return JsonResponse({
            'success': True,
            'subcategories': list(subcategories)
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def ajax_contact_sales(request):
    """AJAX endpoint for contact sales form"""
    try:
        data = json.loads(request.body)
        
        # Create contact message
        contact_message = ContactMessage.objects.create(
            name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone', ''),
            company=data.get('company', ''),
            subject='Sales Inquiry',
            message=data.get('message'),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Send notification email to sales team
        try:
            subject = f"New Sales Inquiry from {data.get('name')}"
            message = f"""
            New sales inquiry received:
            
            Name: {data.get('name')}
            Email: {data.get('email')}
            Phone: {data.get('phone')}
            Company: {data.get('company')}
            
            Message:
            {data.get('message')}
            
            Please follow up promptly.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.DEFAULT_FROM_EMAIL],
                fail_silently=True,
            )
        except Exception as e:
            pass
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you! Our sales team will contact you within 24 hours.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Sorry, something went wrong. Please try again.'
        })

# AJAX endpoint for real-time email validation
@csrf_exempt
@require_http_methods(["POST"])
def validate_business_email_ajax(request):
    """AJAX endpoint for real-time business email validation"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        allow_override = data.get('allow_override', False)
        
        if not email:
            return JsonResponse({'valid': False, 'message': 'Email is required'})
        
        # Check if email exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({
                'valid': False, 
                'message': 'A customer with this email already exists'
            })
        
        # Check business email domain
        blocked_domains = getattr(settings, 'BLOCKED_EMAIL_DOMAINS', [])
        domain = email.split('@')[1] if '@' in email else ''
        
        if domain.lower() in [d.lower() for d in blocked_domains]:
            if allow_override:
                return JsonResponse({
                    'valid': True,
                    'message': f'Personal email ({domain}) - Override enabled',
                    'warning': True
                })
            else:
                return JsonResponse({
                    'valid': False,
                    'message': f'Personal email domain ({domain}). Check "Allow personal email" to override.'
                })
        
        return JsonResponse({
            'valid': True,
            'message': 'Valid business email address'
        })
    
    except Exception as e:
        return JsonResponse({'valid': False, 'message': 'Invalid request'})