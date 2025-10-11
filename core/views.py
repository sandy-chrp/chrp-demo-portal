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
from enquiries.models import BusinessEnquiry, EnquiryResponse, EnquiryCategory
from demos.models import Demo, DemoRequest, DemoView, DemoLike, DemoCategory
from enquiries.models import BusinessEnquiry
from notifications.models import Notification, SystemAnnouncement
from .models import SiteSettings, ContactMessage
from django.db.models.functions import ExtractHour

# FIXED - Correct import from accounts app


# Helper function to check if user is admin
def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def custom_404(request, exception=None):
    """Custom 404 error handler"""
    return render(request, '404.html', status=404)

def custom_500(request):
    """Custom 500 error handler"""
    return render(request, '500.html', status=500)

# =====================================
# CUSTOMER PORTAL VIEWS

@login_required
@user_passes_test(is_admin)
def admin_dashboard_view(request):
    """Main admin dashboard with statistics and demographics - OPTIMIZED"""
    
    # Get activity period from request
    activity_period = request.GET.get('period', 'daily')
    
    # Date ranges for statistics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # ===== BASIC STATS (Fast Queries) =====
    # Use select_related and prefetch_related to reduce queries
    
    # User Statistics - FILTER OUT ADMIN/STAFF USERS
    user_base_query = User.objects.filter(is_staff=False, is_superuser=False)
    
    total_users = user_base_query.count()
    new_users_today = user_base_query.filter(created_at__date=today).count()
    new_users_week = user_base_query.filter(created_at__date__gte=week_ago).count()
    pending_approvals = user_base_query.filter(is_approved=False, is_active=True).count()
    active_users = user_base_query.filter(is_active=True, is_approved=True).count()
    
    # Demo Statistics (Optimized)
    total_demos = Demo.objects.count()
    active_demos = Demo.objects.filter(is_active=True).count()
    total_demo_views = DemoView.objects.count()
    demo_views_today = DemoView.objects.filter(viewed_at__date=today).count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    # Enquiry Statistics (Optimized)
    total_enquiries = BusinessEnquiry.objects.count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    new_enquiries_today = BusinessEnquiry.objects.filter(created_at__date=today).count()
    
    # ===== RECENT ACTIVITY (Limited to 5, Optimized) =====
    recent_users = user_base_query.only('id', 'first_name', 'last_name', 'email', 'organization', 'created_at').order_by('-created_at')[:5]
    recent_enquiries = BusinessEnquiry.objects.only('id', 'first_name', 'last_name', 'enquiry_id', 'organization', 'created_at').order_by('-created_at')[:5]
    recent_demo_requests = DemoRequest.objects.select_related('user', 'demo').only(
        'id', 'requested_date', 'status', 'created_at',
        'user__first_name', 'user__last_name', 'user__organization',
        'demo__title'
    ).order_by('-created_at')[:5]
    
    # ===== POPULAR DEMOS (Optimized) =====
    popular_demos = Demo.objects.annotate(
        views_count_calc=Count('demo_views')
    ).only('id', 'title', 'is_featured', 'is_active', 'likes_count', 'created_at').order_by('-views_count_calc')[:5]
    
    # ===== USER REGISTRATION DATA (Simplified for performance) =====
    monthly_users = []
    if activity_period == 'monthly':
        # Last 6 months only
        for i in range(6):
            date = today.replace(day=1) - timedelta(days=i*30)
            count = user_base_query.filter(
                created_at__year=date.year,
                created_at__month=date.month
            ).count()
            monthly_users.append({'month': date.strftime('%b %Y'), 'count': count})
        monthly_users.reverse()
    else:
        # Last 7 days (daily)
        for i in range(7):
            date = today - timedelta(days=i)
            count = user_base_query.filter(created_at__date=date).count()
            monthly_users.append({'month': date.strftime('%m/%d'), 'count': count})
        monthly_users.reverse()
    
    # ===== WEEKLY ACTIVITY (Last 7 days only) =====
    weekly_activity = []
    for i in range(7):
        date = today - timedelta(days=i)
        weekly_activity.append({
            'date': date.strftime('%m/%d'),
            'demo_views': DemoView.objects.filter(viewed_at__date=date).count(),
            'enquiries': BusinessEnquiry.objects.filter(created_at__date=date).count(),
            'signups': user_base_query.filter(created_at__date=date).count(),
        })
    weekly_activity.reverse()
    
    # ===== DEMOGRAPHICS (Top 10 only) =====
    country_distribution = user_base_query.exclude(
        Q(country_code__isnull=True) | Q(country_code='')
    ).values('country_code').annotate(count=Count('id')).order_by('-count')[:10]
    
    # Country mapping (simplified)
    PHONE_CODE_TO_COUNTRY = {
        '+91': 'India', '+1': 'USA/Canada', '+44': 'UK', '+61': 'Australia',
        '+86': 'China', '+81': 'Japan', '+82': 'South Korea', '+49': 'Germany',
        '+33': 'France', '+39': 'Italy', '+34': 'Spain', '+92': 'Pakistan',
        '+971': 'UAE', '+966': 'Saudi Arabia', '+65': 'Singapore',
    }
    
    country_data = [
        {
            'country': PHONE_CODE_TO_COUNTRY.get(item['country_code'], item['country_code']),
            'count': item['count']
        }
        for item in country_distribution
    ]
    
    # ===== SOURCE DATA (Optimized) =====
    source_distribution = user_base_query.values('referral_source').annotate(
        count=Count('id')
    ).order_by('-count')
    
    source_labels = {
        'referral': 'Referral from colleague', 'facebook': 'Facebook',
        'youtube': 'YouTube', 'linkedin': 'LinkedIn',
        'google': 'Google Search', 'other': 'Other',
        '': 'Not Specified', None: 'Not Specified'
    }
    
    source_data = []
    for item in source_distribution:
        source_value = item['referral_source'] or ''
        source_name = source_labels.get(source_value, 'Not Specified')
        existing = next((x for x in source_data if x['source'] == source_name), None)
        if existing:
            existing['count'] += item['count']
        else:
            source_data.append({'source': source_name, 'count': item['count']})
    
    # ===== ACTIVITY ANALYTICS (Lazy Load - Only basic stats) =====
    # Heavy queries moved to AJAX endpoint for better performance
    activity_stats = {
        'active_users': 0,
        'active_users_change': 0,
        'total_views': total_demo_views,
        'views_change': 0,
        'demo_requests': demo_requests_pending,
        'requests_change': 0,
        'enquiries': open_enquiries,
        'enquiries_change': 0,
    }
    
    context = {
        # Basic Stats
        'total_users': total_users,
        'new_users_today': new_users_today,
        'new_users_week': new_users_week,
        'pending_approvals': pending_approvals,
        'active_users': active_users,
        'total_demos': total_demos,
        'active_demos': active_demos,
        'total_demo_views': total_demo_views,
        'demo_views_today': demo_views_today,
        'demo_requests_pending': demo_requests_pending,
        'total_enquiries': total_enquiries,
        'open_enquiries': open_enquiries,
        'new_enquiries_today': new_enquiries_today,
        
        # Recent Activity
        'recent_users': recent_users,
        'recent_enquiries': recent_enquiries,
        'recent_demo_requests': recent_demo_requests,
        'recent_contact_messages': [],
        'popular_demos': popular_demos,
        
        # Chart Data
        'monthly_users': monthly_users,
        'weekly_activity': weekly_activity,
        'country_data': country_data,
        'source_data': source_data,
        
        # Activity Analytics (Minimal for initial load)
        'activity_stats': activity_stats,
        'user_activity_data': [],  # Load via AJAX
        'peak_hours': [],  # Load via AJAX
        'most_active_users': [],  # Load via AJAX
        'activity_period': activity_period,
        'system_health': {'database': 'healthy', 'email': 'healthy'},
    }
    
    return render(request, 'admin/dashboard.html', context)
    
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
    
    # Popular Demos (most viewed)
    popular_demos = Demo.objects.annotate(
        views_count_calc=Count('demo_views')
    ).order_by('-views_count_calc')[:5]
    
    # ============ DYNAMIC USER REGISTRATION DATA (WITH FILTERS) ============
    end_date = timezone.now()
    
    if activity_period == 'daily':
        start_date = end_date - timedelta(days=7)  # Last 7 days
        date_format = '%m/%d'
    elif activity_period == 'weekly':
        start_date = end_date - timedelta(weeks=12)  # Last 12 weeks
        date_format = 'Week %W'
    elif activity_period == 'monthly':
        start_date = end_date - timedelta(days=365)  # Last 12 months
        date_format = '%b %Y'
    elif activity_period == 'custom':
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        if start_date_str and end_date_str:
            from datetime import datetime
            start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d'))
        else:
            start_date = end_date - timedelta(days=30)
        date_format = '%m/%d'
    else:
        start_date = end_date - timedelta(days=7)
        date_format = '%m/%d'
    
    # Monthly User Growth Chart Data
    monthly_users = []
    
    if activity_period == 'monthly':
        # Monthly breakdown for last 12 months
        for i in range(12):
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
    elif activity_period == 'weekly':
        # Weekly breakdown for last 12 weeks
        current_date = start_date.date()
        while current_date <= end_date.date():
            week_end = current_date + timedelta(days=6)
            count = User.objects.filter(
                created_at__date__range=[current_date, week_end],
                is_staff=False,
                is_superuser=False
            ).count()
            monthly_users.append({
                'month': f"Week {current_date.strftime('%W')}",
                'count': count
            })
            current_date = week_end + timedelta(days=1)
    else:
        # Daily breakdown
        current_date = start_date.date()
        while current_date <= end_date.date():
            count = User.objects.filter(
                created_at__date=current_date,
                is_staff=False,
                is_superuser=False
            ).count()
            monthly_users.append({
                'month': current_date.strftime(date_format),
                'count': count
            })
            current_date += timedelta(days=1)
    
    # Weekly Activity Data (always last 7 days)
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
    
    # ============ USER DEMOGRAPHICS BY COUNTRY ============
    country_distribution = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).exclude(
        Q(country_code__isnull=True) | Q(country_code='')
    ).values('country_code').annotate(
        count=Count('id')
    ).order_by('-count')[:10]  # Top 10 countries
    
    # Phone code to country name mapping
    PHONE_CODE_TO_COUNTRY = {
        '+91': 'India', '+1': 'USA/Canada', '+44': 'United Kingdom', '+61': 'Australia',
        '+86': 'China', '+81': 'Japan', '+82': 'South Korea', '+49': 'Germany',
        '+33': 'France', '+39': 'Italy', '+34': 'Spain', '+7': 'Russia/Kazakhstan',
        '+52': 'Mexico', '+55': 'Brazil', '+62': 'Indonesia', '+63': 'Philippines',
        '+60': 'Malaysia', '+65': 'Singapore', '+66': 'Thailand', '+84': 'Vietnam',
        '+92': 'Pakistan', '+880': 'Bangladesh', '+94': 'Sri Lanka', '+977': 'Nepal',
        '+971': 'UAE', '+966': 'Saudi Arabia', '+27': 'South Africa', '+234': 'Nigeria',
        '+254': 'Kenya', '+20': 'Egypt', '+30': 'Greece', '+31': 'Netherlands',
        '+41': 'Switzerland', '+46': 'Sweden', '+47': 'Norway', '+48': 'Poland',
        '+351': 'Portugal', '+353': 'Ireland', '+358': 'Finland', '+380': 'Ukraine',
        '+420': 'Czech Republic', '+43': 'Austria', '+45': 'Denmark', '+90': 'Turkey',
    }
    
    # Format country data for chart
    country_data = []
    for item in country_distribution:
        phone_code = item['country_code']
        country_name = PHONE_CODE_TO_COUNTRY.get(phone_code, phone_code)
        country_data.append({
            'country': country_name,
            'count': item['count']
        })
    
    # Add "Not Specified" if there are users without country_code
    users_without_country = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).filter(
        Q(country_code__isnull=True) | Q(country_code='')
    ).count()
    
    if users_without_country > 0:
        country_data.append({
            'country': 'Not Specified',
            'count': users_without_country
        })
    
    # ============ USER SOURCE TRACKING ============
    source_distribution = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).values('referral_source').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Format source data for chart
    source_data = []
    source_labels = {
        'referral': 'Referral from colleague',
        'facebook': 'Facebook',
        'youtube': 'YouTube',
        'linkedin': 'LinkedIn',
        'google': 'Google Search',
        'other': 'Other',
        '': 'Not Specified',
        None: 'Not Specified'
    }
    
    for item in source_distribution:
        source_value = item['referral_source'] if item['referral_source'] else ''
        source_name = source_labels.get(source_value, 'Not Specified')
        
        # Avoid duplicate "Not Specified" entries
        existing = next((x for x in source_data if x['source'] == source_name), None)
        if existing:
            existing['count'] += item['count']
        else:
            source_data.append({
                'source': source_name,
                'count': item['count']
            })
    
    # ============ USER ACTIVITY ANALYTICS ============
    # Calculate date range based on period
    period_duration = (end_date.date() - start_date.date()).days
    previous_period_end = start_date
    previous_period_start = previous_period_end - timedelta(days=period_duration)
    
    # Active Users (users who performed any activity)
    current_active_users = User.objects.filter(
        Q(demo_views__viewed_at__range=[start_date, end_date]) |
        Q(demo_requests__created_at__range=[start_date, end_date]) |
        Q(enquiries__created_at__range=[start_date, end_date]),
        is_staff=False,
        is_superuser=False
    ).distinct().count()
    
    previous_active_users = User.objects.filter(
        Q(demo_views__viewed_at__range=[previous_period_start, previous_period_end]) |
        Q(demo_requests__created_at__range=[previous_period_start, previous_period_end]) |
        Q(enquiries__created_at__range=[previous_period_start, previous_period_end]),
        is_staff=False,
        is_superuser=False
    ).distinct().count()
    
    active_users_change = ((current_active_users - previous_active_users) / max(previous_active_users, 1)) * 100 if previous_active_users > 0 else 0
    
    # Total Views
    current_views = DemoView.objects.filter(viewed_at__range=[start_date, end_date]).count()
    previous_views = DemoView.objects.filter(viewed_at__range=[previous_period_start, previous_period_end]).count()
    views_change = ((current_views - previous_views) / max(previous_views, 1)) * 100 if previous_views > 0 else 0
    
    # Demo Requests
    current_requests = DemoRequest.objects.filter(created_at__range=[start_date, end_date]).count()
    previous_requests = DemoRequest.objects.filter(created_at__range=[previous_period_start, previous_period_end]).count()
    requests_change = ((current_requests - previous_requests) / max(previous_requests, 1)) * 100 if previous_requests > 0 else 0
    
    # Enquiries
    current_enquiries = BusinessEnquiry.objects.filter(created_at__range=[start_date, end_date]).count()
    previous_enquiries = BusinessEnquiry.objects.filter(created_at__range=[previous_period_start, previous_period_end]).count()
    enquiries_change = ((current_enquiries - previous_enquiries) / max(previous_enquiries, 1)) * 100 if previous_enquiries > 0 else 0
    
    activity_stats = {
        'active_users': current_active_users,
        'active_users_change': round(active_users_change, 1),
        'total_views': current_views,
        'views_change': round(views_change, 1),
        'demo_requests': current_requests,
        'requests_change': round(requests_change, 1),
        'enquiries': current_enquiries,
        'enquiries_change': round(enquiries_change, 1),
    }
    
    # User Activity Timeline Data
    user_activity_data = []
    current_date = start_date.date()
    while current_date <= end_date.date():
        date_start = timezone.make_aware(timezone.datetime.combine(current_date, timezone.datetime.min.time()))
        date_end = timezone.make_aware(timezone.datetime.combine(current_date, timezone.datetime.max.time()))
        
        views = DemoView.objects.filter(viewed_at__range=[date_start, date_end]).count()
        requests = DemoRequest.objects.filter(created_at__range=[date_start, date_end]).count()
        enquiries_count = BusinessEnquiry.objects.filter(created_at__range=[date_start, date_end]).count()
        logins = User.objects.filter(
            last_login__range=[date_start, date_end],
            is_staff=False,
            is_superuser=False
        ).count()
        
        user_activity_data.append({
            'date': current_date.strftime(date_format),
            'views': views,
            'requests': requests,
            'enquiries': enquiries_count,
            'logins': logins,
        })
        
        current_date += timedelta(days=1)
    
    # Peak Activity Hours (last 30 days)
    last_30_days = timezone.now() - timedelta(days=30)
    
    # Get activity by hour
    demo_view_hours = DemoView.objects.filter(
        viewed_at__gte=last_30_days
    ).annotate(hour=ExtractHour('viewed_at')).values('hour').annotate(count=Count('id'))
    
    demo_request_hours = DemoRequest.objects.filter(
        created_at__gte=last_30_days
    ).annotate(hour=ExtractHour('created_at')).values('hour').annotate(count=Count('id'))
    
    enquiry_hours = BusinessEnquiry.objects.filter(
        created_at__gte=last_30_days
    ).annotate(hour=ExtractHour('created_at')).values('hour').annotate(count=Count('id'))
    
    # Aggregate by hour
    hour_counts = {}
    for item in demo_view_hours:
        hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
    for item in demo_request_hours:
        hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
    for item in enquiry_hours:
        hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
    
    # Sort and format
    total_activities = sum(hour_counts.values())
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    peak_hours_data = []
    for hour, count in sorted_hours:
        start_hour = f"{hour:02d}:00"
        end_hour = f"{(hour+1):02d}:00"
        time_slot = f"{start_hour} - {end_hour}"
        percentage = (count / total_activities * 100) if total_activities > 0 else 0
        
        peak_hours_data.append({
            'time_slot': time_slot,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    # Most Active Users (last 30 days)
    most_active_users_data = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).annotate(
        activity_count=(
            Count('demo_views', filter=Q(demo_views__viewed_at__gte=last_30_days)) + 
            Count('demo_requests', filter=Q(demo_requests__created_at__gte=last_30_days)) + 
            Count('enquiries', filter=Q(enquiries__created_at__gte=last_30_days))
        )
    ).filter(activity_count__gt=0).order_by('-activity_count')[:10]
    
    context = {
        # User Stats
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
        'recent_contact_messages': [],
        'popular_demos': popular_demos,
        
        # Chart Data
        'monthly_users': monthly_users,
        'weekly_activity': weekly_activity,
        'system_health': system_health,
        
        # Demographics Data
        'country_data': country_data,
        'source_data': source_data,
        
        # Activity Analytics
        'activity_stats': activity_stats,
        'user_activity_data': user_activity_data,
        'peak_hours': peak_hours_data,
        'most_active_users': most_active_users_data,
        'activity_period': activity_period,
    }
    
    return render(request, 'admin/dashboard.html', context)

# =====================================

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
    """Main admin dashboard with statistics and demographics"""
    
    # Get activity period from request
    activity_period = request.GET.get('period', 'daily')
    
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
    
    # Popular Demos (most viewed)
    popular_demos = Demo.objects.annotate(
        views_count_calc=Count('demo_views')
    ).order_by('-views_count_calc')[:5]
    
    # ============ DYNAMIC USER REGISTRATION DATA (WITH FILTERS) ============
    end_date = timezone.now()
    
    if activity_period == 'daily':
        start_date = end_date - timedelta(days=7)  # Last 7 days
        date_format = '%m/%d'
    elif activity_period == 'weekly':
        start_date = end_date - timedelta(weeks=12)  # Last 12 weeks
        date_format = 'Week %W'
    elif activity_period == 'monthly':
        start_date = end_date - timedelta(days=365)  # Last 12 months
        date_format = '%b %Y'
    elif activity_period == 'custom':
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        if start_date_str and end_date_str:
            from datetime import datetime
            start_date = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d'))
        else:
            start_date = end_date - timedelta(days=30)
        date_format = '%m/%d'
    else:
        start_date = end_date - timedelta(days=7)
        date_format = '%m/%d'
    
    # Monthly User Growth Chart Data
    monthly_users = []
    
    if activity_period == 'monthly':
        # Monthly breakdown for last 12 months
        for i in range(12):
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
    elif activity_period == 'weekly':
        # Weekly breakdown for last 12 weeks
        current_date = start_date.date()
        while current_date <= end_date.date():
            week_end = current_date + timedelta(days=6)
            count = User.objects.filter(
                created_at__date__range=[current_date, week_end],
                is_staff=False,
                is_superuser=False
            ).count()
            monthly_users.append({
                'month': f"Week {current_date.strftime('%W')}",
                'count': count
            })
            current_date = week_end + timedelta(days=1)
    else:
        # Daily breakdown
        current_date = start_date.date()
        while current_date <= end_date.date():
            count = User.objects.filter(
                created_at__date=current_date,
                is_staff=False,
                is_superuser=False
            ).count()
            monthly_users.append({
                'month': current_date.strftime(date_format),
                'count': count
            })
            current_date += timedelta(days=1)
    
    # Weekly Activity Data (always last 7 days)
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
    
    # ============ USER DEMOGRAPHICS BY COUNTRY ============
    country_distribution = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).exclude(
        Q(country_code__isnull=True) | Q(country_code='')
    ).values('country_code').annotate(
        count=Count('id')
    ).order_by('-count')[:10]  # Top 10 countries
    
    # Phone code to country name mapping
    PHONE_CODE_TO_COUNTRY = {
        '+91': 'India', '+1': 'USA/Canada', '+44': 'United Kingdom', '+61': 'Australia',
        '+86': 'China', '+81': 'Japan', '+82': 'South Korea', '+49': 'Germany',
        '+33': 'France', '+39': 'Italy', '+34': 'Spain', '+7': 'Russia/Kazakhstan',
        '+52': 'Mexico', '+55': 'Brazil', '+62': 'Indonesia', '+63': 'Philippines',
        '+60': 'Malaysia', '+65': 'Singapore', '+66': 'Thailand', '+84': 'Vietnam',
        '+92': 'Pakistan', '+880': 'Bangladesh', '+94': 'Sri Lanka', '+977': 'Nepal',
        '+971': 'UAE', '+966': 'Saudi Arabia', '+27': 'South Africa', '+234': 'Nigeria',
        '+254': 'Kenya', '+20': 'Egypt', '+30': 'Greece', '+31': 'Netherlands',
        '+41': 'Switzerland', '+46': 'Sweden', '+47': 'Norway', '+48': 'Poland',
        '+351': 'Portugal', '+353': 'Ireland', '+358': 'Finland', '+380': 'Ukraine',
        '+420': 'Czech Republic', '+43': 'Austria', '+45': 'Denmark', '+90': 'Turkey',
    }
    
    # Format country data for chart
    country_data = []
    for item in country_distribution:
        phone_code = item['country_code']
        country_name = PHONE_CODE_TO_COUNTRY.get(phone_code, phone_code)
        country_data.append({
            'country': country_name,
            'count': item['count']
        })
    
    # Add "Not Specified" if there are users without country_code
    users_without_country = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).filter(
        Q(country_code__isnull=True) | Q(country_code='')
    ).count()
    
    if users_without_country > 0:
        country_data.append({
            'country': 'Not Specified',
            'count': users_without_country
        })
    
    # ============ USER SOURCE TRACKING ============
    source_distribution = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).values('referral_source').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Format source data for chart
    source_data = []
    source_labels = {
        'referral': 'Referral from colleague',
        'facebook': 'Facebook',
        'youtube': 'YouTube',
        'linkedin': 'LinkedIn',
        'google': 'Google Search',
        'other': 'Other',
        '': 'Not Specified',
        None: 'Not Specified'
    }
    
    for item in source_distribution:
        source_value = item['referral_source'] if item['referral_source'] else ''
        source_name = source_labels.get(source_value, 'Not Specified')
        
        # Avoid duplicate "Not Specified" entries
        existing = next((x for x in source_data if x['source'] == source_name), None)
        if existing:
            existing['count'] += item['count']
        else:
            source_data.append({
                'source': source_name,
                'count': item['count']
            })
    
    # ============ USER ACTIVITY ANALYTICS ============
    # Calculate date range based on period
    period_duration = (end_date.date() - start_date.date()).days
    previous_period_end = start_date
    previous_period_start = previous_period_end - timedelta(days=period_duration)
    
    # Active Users (users who performed any activity)
    current_active_users = User.objects.filter(
        Q(demo_views__viewed_at__range=[start_date, end_date]) |
        Q(demo_requests__created_at__range=[start_date, end_date]) |
        Q(enquiries__created_at__range=[start_date, end_date]),
        is_staff=False,
        is_superuser=False
    ).distinct().count()
    
    previous_active_users = User.objects.filter(
        Q(demo_views__viewed_at__range=[previous_period_start, previous_period_end]) |
        Q(demo_requests__created_at__range=[previous_period_start, previous_period_end]) |
        Q(enquiries__created_at__range=[previous_period_start, previous_period_end]),
        is_staff=False,
        is_superuser=False
    ).distinct().count()
    
    active_users_change = ((current_active_users - previous_active_users) / max(previous_active_users, 1)) * 100 if previous_active_users > 0 else 0
    
    # Total Views
    current_views = DemoView.objects.filter(viewed_at__range=[start_date, end_date]).count()
    previous_views = DemoView.objects.filter(viewed_at__range=[previous_period_start, previous_period_end]).count()
    views_change = ((current_views - previous_views) / max(previous_views, 1)) * 100 if previous_views > 0 else 0
    
    # Demo Requests
    current_requests = DemoRequest.objects.filter(created_at__range=[start_date, end_date]).count()
    previous_requests = DemoRequest.objects.filter(created_at__range=[previous_period_start, previous_period_end]).count()
    requests_change = ((current_requests - previous_requests) / max(previous_requests, 1)) * 100 if previous_requests > 0 else 0
    
    # Enquiries
    current_enquiries = BusinessEnquiry.objects.filter(created_at__range=[start_date, end_date]).count()
    previous_enquiries = BusinessEnquiry.objects.filter(created_at__range=[previous_period_start, previous_period_end]).count()
    enquiries_change = ((current_enquiries - previous_enquiries) / max(previous_enquiries, 1)) * 100 if previous_enquiries > 0 else 0
    
    activity_stats = {
        'active_users': current_active_users,
        'active_users_change': round(active_users_change, 1),
        'total_views': current_views,
        'views_change': round(views_change, 1),
        'demo_requests': current_requests,
        'requests_change': round(requests_change, 1),
        'enquiries': current_enquiries,
        'enquiries_change': round(enquiries_change, 1),
    }
    
    # User Activity Timeline Data
    user_activity_data = []
    current_date = start_date.date()
    while current_date <= end_date.date():
        date_start = timezone.make_aware(timezone.datetime.combine(current_date, timezone.datetime.min.time()))
        date_end = timezone.make_aware(timezone.datetime.combine(current_date, timezone.datetime.max.time()))
        
        views = DemoView.objects.filter(viewed_at__range=[date_start, date_end]).count()
        requests = DemoRequest.objects.filter(created_at__range=[date_start, date_end]).count()
        enquiries_count = BusinessEnquiry.objects.filter(created_at__range=[date_start, date_end]).count()
        logins = User.objects.filter(
            last_login__range=[date_start, date_end],
            is_staff=False,
            is_superuser=False
        ).count()
        
        user_activity_data.append({
            'date': current_date.strftime(date_format),
            'views': views,
            'requests': requests,
            'enquiries': enquiries_count,
            'logins': logins,
        })
        
        current_date += timedelta(days=1)
    
    # Peak Activity Hours (last 30 days)
    last_30_days = timezone.now() - timedelta(days=30)
    
    # Get activity by hour
    demo_view_hours = DemoView.objects.filter(
        viewed_at__gte=last_30_days
    ).annotate(hour=ExtractHour('viewed_at')).values('hour').annotate(count=Count('id'))
    
    demo_request_hours = DemoRequest.objects.filter(
        created_at__gte=last_30_days
    ).annotate(hour=ExtractHour('created_at')).values('hour').annotate(count=Count('id'))
    
    enquiry_hours = BusinessEnquiry.objects.filter(
        created_at__gte=last_30_days
    ).annotate(hour=ExtractHour('created_at')).values('hour').annotate(count=Count('id'))
    
    # Aggregate by hour
    hour_counts = {}
    for item in demo_view_hours:
        hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
    for item in demo_request_hours:
        hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
    for item in enquiry_hours:
        hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
    
    # Sort and format
    total_activities = sum(hour_counts.values())
    sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    peak_hours_data = []
    for hour, count in sorted_hours:
        start_hour = f"{hour:02d}:00"
        end_hour = f"{(hour+1):02d}:00"
        time_slot = f"{start_hour} - {end_hour}"
        percentage = (count / total_activities * 100) if total_activities > 0 else 0
        
        peak_hours_data.append({
            'time_slot': time_slot,
            'count': count,
            'percentage': round(percentage, 1)
        })
    
    # Most Active Users (last 30 days)
    most_active_users_data = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).annotate(
        activity_count=(
            Count('demo_views', filter=Q(demo_views__viewed_at__gte=last_30_days)) + 
            Count('demo_requests', filter=Q(demo_requests__created_at__gte=last_30_days)) + 
            Count('enquiries', filter=Q(enquiries__created_at__gte=last_30_days))
        )
    ).filter(activity_count__gt=0).order_by('-activity_count')[:10]
    
    context = {
        # User Stats
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
        'recent_contact_messages': [],
        'popular_demos': popular_demos,
        
        # Chart Data
        'monthly_users': monthly_users,
        'weekly_activity': weekly_activity,
        'system_health': system_health,
        
        # Demographics Data
        'country_data': country_data,
        'source_data': source_data,
        
        # Activity Analytics
        'activity_stats': activity_stats,
        'user_activity_data': user_activity_data,
        'peak_hours': peak_hours_data,
        'most_active_users': most_active_users_data,
        'activity_period': activity_period,
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
    """Admin demos management - UPDATED WITH WEBGL SUPPORT"""
    
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
    file_type_filter = request.GET.get('file_type')  # NEW: File type filter
    demo_type_filter = request.GET.get('demo_type')
    business_category_filter = request.GET.get('business_category')
    status_filter = request.GET.get('status')
    featured_filter = request.GET.get('featured')
    
    if search:
        demos_list = demos_list.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search)
        )
    
    # NEW: File type filtering
    if file_type_filter:
        demos_list = demos_list.filter(file_type=file_type_filter)
    
    if demo_type_filter:
        demos_list = demos_list.filter(demo_type=demo_type_filter)
    
    if business_category_filter:
        demos_list = demos_list.filter(
            Q(target_business_categories__id=business_category_filter) |
            Q(target_business_subcategories__category__id=business_category_filter)
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
    
    # Statistics - UPDATED
    stats = {
        'total': Demo.objects.count(),
        'active': Demo.objects.filter(is_active=True).count(),
        'inactive': Demo.objects.filter(is_active=False).count(),
        'featured': Demo.objects.filter(is_featured=True).count(),
        'total_views': Demo.objects.aggregate(total=Sum('views_count'))['total'] or 0,
        'video_count': Demo.objects.filter(file_type='video').count(),  # NEW
        'webgl_count': Demo.objects.filter(file_type='webgl').count(),  # NEW
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
        'file_types': Demo.FILE_TYPE_CHOICES,  # NEW
        'stats': stats,
        'search': search,
        'file_type_filter': file_type_filter,  # NEW
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
    """Admin add new demo - WITH MANDATORY CATEGORY SELECTION (No file size limits)"""
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        demo_type = request.POST.get('demo_type', 'product')
        file_type = request.POST.get('file_type', 'video')
        
        video_file = request.FILES.get('video_file')
        webgl_file = request.FILES.get('webgl_file')
        thumbnail = request.FILES.get('thumbnail')
        duration = request.POST.get('duration', '').strip()
        
        is_featured = request.POST.get('is_featured') == 'on'
        is_active = request.POST.get('is_active', 'on') == 'on'
        sort_order = request.POST.get('sort_order', '0')
        
        # Get business categories
        all_business_categories = request.POST.get('allBusinessCategoriesCheckbox') == 'on'
        business_category_ids = request.POST.getlist('target_business_categories')
        business_subcategory_ids = request.POST.getlist('target_business_subcategories')
        
        # Get target customers
        customer_ids = request.POST.getlist('target_customers')
        
        try:
            # Validate required fields
            if not title:
                messages.error(request, 'Title is required.')
                return redirect('core:admin_add_demo')
            
            if not description:
                messages.error(request, 'Description is required.')
                return redirect('core:admin_add_demo')
            
            if not thumbnail:
                messages.error(request, 'Thumbnail image is required.')
                return redirect('core:admin_add_demo')
            
            # Validate business category selection
            if not all_business_categories and not business_category_ids:
                messages.error(request, 'Please select at least one business category or enable "Available to All Business Categories".')
                return redirect('core:admin_add_demo')
            
            # Validate file based on file_type
            if file_type == 'video':
                if not video_file:
                    messages.error(request, 'Video file is required when file type is Video.')
                    return redirect('core:admin_add_demo')
                
                # Validate video file extension only
                video_ext = video_file.name.split('.')[-1].lower()
                if video_ext not in ['mp4', 'avi', 'mov', 'wmv']:
                    messages.error(request, 'Invalid video format. Allowed: MP4, AVI, MOV, WMV')
                    return redirect('core:admin_add_demo')
            
            elif file_type == 'webgl':
                if not webgl_file:
                    messages.error(request, 'WebGL file is required when file type is WebGL.')
                    return redirect('core:admin_add_demo')
                
                # Validate webgl file extension only
                webgl_ext = webgl_file.name.split('.')[-1].lower()
                if webgl_ext not in ['html', 'zip', 'gltf', 'glb']:
                    messages.error(request, 'Invalid WebGL format. Allowed: HTML, ZIP, GLTF, GLB')
                    return redirect('core:admin_add_demo')
            
            else:
                messages.error(request, 'Invalid file type selected.')
                return redirect('core:admin_add_demo')
            
            # Validate thumbnail extension only
            thumbnail_ext = thumbnail.name.split('.')[-1].lower()
            if thumbnail_ext not in ['jpg', 'jpeg', 'png', 'webp']:
                messages.error(request, 'Invalid thumbnail format. Allowed: JPG, PNG, WebP')
                return redirect('core:admin_add_demo')
            
            # Convert sort_order to integer
            try:
                sort_order = int(sort_order)
            except ValueError:
                sort_order = 0
            
            # Create demo
            demo = Demo.objects.create(
                title=title,
                description=description,
                demo_type=demo_type,
                file_type=file_type,
                video_file=video_file if file_type == 'video' else None,
                webgl_file=webgl_file if file_type == 'webgl' else None,
                thumbnail=thumbnail,
                is_featured=is_featured,
                is_active=is_active,
                sort_order=sort_order,
                created_by=request.user
            )
            
            # Set duration if provided (only for videos)
            if file_type == 'video' and duration:
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
                except (ValueError, TypeError):
                    pass  # Invalid duration format, skip
            
            # Set business categories - ONLY if NOT all categories
            if not all_business_categories:
                if business_category_ids:
                    from accounts.models import BusinessCategory
                    categories = BusinessCategory.objects.filter(id__in=business_category_ids)
                    demo.target_business_categories.set(categories)
                
                # Set business subcategories
                if business_subcategory_ids:
                    from accounts.models import BusinessSubCategory
                    subcategories = BusinessSubCategory.objects.filter(id__in=business_subcategory_ids)
                    demo.target_business_subcategories.set(subcategories)
                
                messages.info(request, f'Demo will be available to {len(business_category_ids)} selected business categories.')
            else:
                messages.info(request, 'Demo will be available to all business categories.')
            
            # Set target customers
            if customer_ids:
                from accounts.models import CustomUser
                customers = CustomUser.objects.filter(id__in=customer_ids, is_approved=True)
                demo.target_customers.set(customers)
                messages.info(request, f'Demo will be available to {customers.count()} specific customers.')
            else:
                messages.info(request, 'Demo will be available to all approved customers.')
            
            messages.success(request, f'Demo "{demo.title}" ({demo.get_file_type_display()}) created successfully!')
            return redirect('core:admin_demo_detail', demo_id=demo.id)
            
        except Exception as e:
            messages.error(request, f'Error creating demo: {str(e)}')
            return redirect('core:admin_add_demo')
    
    # GET request - show form
    from accounts.models import BusinessCategory, BusinessSubCategory, CustomUser
    business_categories = BusinessCategory.objects.filter(is_active=True).prefetch_related('subcategories').order_by('sort_order', 'name')
    
    # Get all approved customers for selection
    customers = CustomUser.objects.filter(
        is_approved=True,
        is_active=True
    ).select_related('business_category').order_by('first_name', 'last_name')
    
    # Context for sidebar
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'business_categories': business_categories,
        'customers': customers,
        'demo_types': Demo.DEMO_TYPE_CHOICES,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demos/add.html', context)

@login_required
@user_passes_test(is_admin)
def admin_demo_detail_view(request, demo_id):
    """View and edit demo details - No file size limits"""
    
    demo = get_object_or_404(
        Demo.objects.prefetch_related(
            'target_business_categories',
            'target_business_subcategories',
            'target_customers'
        ).select_related('created_by'),
        id=demo_id
    )
    
    if request.method == 'POST':
        try:
            # Handle form submission for editing
            demo.title = request.POST.get('title', demo.title).strip()
            demo.description = request.POST.get('description', demo.description).strip()
            demo.demo_type = request.POST.get('demo_type', demo.demo_type)
            
            # Handle file type changes
            file_type = request.POST.get('file_type', demo.file_type)
            
            # Validate title and description
            if not demo.title:
                messages.error(request, 'Title is required.')
                return redirect('core:admin_demo_detail', demo_id=demo.id)
            
            if not demo.description:
                messages.error(request, 'Description is required.')
                return redirect('core:admin_demo_detail', demo_id=demo.id)
            
            # Update boolean fields
            demo.is_featured = request.POST.get('is_featured') == 'on'
            demo.is_active = request.POST.get('is_active') == 'on'
            
            # Update sort order
            sort_order = request.POST.get('sort_order', '0')
            try:
                demo.sort_order = int(sort_order)
            except ValueError:
                demo.sort_order = 0
            
            # Handle file type and file uploads
            if file_type != demo.file_type:
                # File type is changing
                demo.file_type = file_type
                
                if file_type == 'video':
                    # Switching to video - clear WebGL file
                    if demo.webgl_file:
                        demo.webgl_file.delete()
                        demo.webgl_file = None
                elif file_type == 'webgl':
                    # Switching to WebGL - clear video file and duration
                    if demo.video_file:
                        demo.video_file.delete()
                        demo.video_file = None
                    demo.duration = None
            
            # Update video file if provided
            if 'video_file' in request.FILES:
                video_file = request.FILES['video_file']
                
                # Validate video file extension only
                video_ext = video_file.name.split('.')[-1].lower()
                if video_ext not in ['mp4', 'avi', 'mov', 'wmv']:
                    messages.error(request, 'Invalid video format. Allowed: MP4, AVI, MOV, WMV')
                    return redirect('core:admin_demo_detail', demo_id=demo.id)
                
                # Delete old video file
                if demo.video_file:
                    demo.video_file.delete()
                
                demo.video_file = video_file
                demo.file_type = 'video'
            
            # Update WebGL file if provided
            if 'webgl_file' in request.FILES:
                webgl_file = request.FILES['webgl_file']
                
                # Validate WebGL file extension only
                webgl_ext = webgl_file.name.split('.')[-1].lower()
                if webgl_ext not in ['html', 'zip', 'gltf', 'glb']:
                    messages.error(request, 'Invalid WebGL format. Allowed: HTML, ZIP, GLTF, GLB')
                    return redirect('core:admin_demo_detail', demo_id=demo.id)
                
                # Delete old WebGL file
                if demo.webgl_file:
                    demo.webgl_file.delete()
                
                demo.webgl_file = webgl_file
                demo.file_type = 'webgl'
            
            # Update thumbnail if provided
            if 'thumbnail' in request.FILES:
                thumbnail = request.FILES['thumbnail']
                
                # Validate thumbnail extension only
                thumbnail_ext = thumbnail.name.split('.')[-1].lower()
                if thumbnail_ext not in ['jpg', 'jpeg', 'png', 'webp']:
                    messages.error(request, 'Invalid thumbnail format. Allowed: JPG, PNG, WebP')
                    return redirect('core:admin_demo_detail', demo_id=demo.id)
                
                # Delete old thumbnail
                if demo.thumbnail:
                    demo.thumbnail.delete()
                
                demo.thumbnail = thumbnail
            
            # Update duration (only for video type)
            if demo.file_type == 'video':
                duration = request.POST.get('duration', '').strip()
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
                    except (ValueError, TypeError):
                        pass  # Invalid duration format, skip
            else:
                # Clear duration for non-video types
                demo.duration = None
            
            demo.save()
            
            # Handle "All Business Categories" checkbox
            all_business_categories = request.POST.get('allBusinessCategoriesCheckbox') == 'on'
            
            if all_business_categories:
                # Clear all category selections
                demo.target_business_categories.clear()
                demo.target_business_subcategories.clear()
                messages.info(request, 'Demo is now available to all business categories.')
            else:
                # Update business categories
                business_category_ids = request.POST.getlist('target_business_categories')
                if business_category_ids:
                    from accounts.models import BusinessCategory
                    categories = BusinessCategory.objects.filter(id__in=business_category_ids)
                    demo.target_business_categories.set(categories)
                    messages.info(request, f'Demo targeted to {categories.count()} business categories.')
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
            
            # Update target customers
            customer_ids = request.POST.getlist('target_customers')
            if customer_ids:
                from accounts.models import CustomUser
                customers = CustomUser.objects.filter(id__in=customer_ids, is_approved=True)
                demo.target_customers.set(customers)
                messages.info(request, f'Demo access updated for {customers.count()} specific customers.')
            else:
                demo.target_customers.clear()
                messages.info(request, 'Demo is now available to all approved customers.')
            
            messages.success(request, f'Demo "{demo.title}" ({demo.get_file_type_display()}) has been updated successfully!')
            return redirect('core:admin_demo_detail', demo_id=demo.id)
            
        except Exception as e:
            messages.error(request, f'Error updating demo: {str(e)}')
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
    business_categories = BusinessCategory.objects.filter(is_active=True).prefetch_related('subcategories').order_by('sort_order', 'name')
    
    # Get all approved customers for selection
    customers = CustomUser.objects.filter(
        is_approved=True,
        is_active=True
    ).select_related('business_category').order_by('first_name', 'last_name')
    
    # Context for sidebar
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'demo': demo,
        'demo_types': Demo.DEMO_TYPE_CHOICES,
        'file_types': Demo.FILE_TYPE_CHOICES,
        'business_categories': business_categories,
        'customers': customers,
        'total_views': total_views,
        'total_likes': total_likes,
        'total_requests': total_requests,
        'target_customers': target_customers,
        'total_accessible_customers': total_accessible_customers,
        'is_for_all_customers': demo.is_for_all_customers,
        'is_for_all_business_categories': demo.is_for_all_business_categories,
        'recent_views': recent_views,
        'recent_requests': recent_requests,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demos/detail.html', context)

@login_required
@user_passes_test(is_admin)
def admin_demo_watch_view(request, demo_id):
    """
    Admin watch/preview demo - handles both video and WebGL
    Auto-redirects WebGL to WebGL viewer
    """
    demo = get_object_or_404(Demo, id=demo_id)
    
    # Context for sidebar
    from accounts.models import CustomUser
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    # ✅ NEW: Auto-redirect WebGL demos to WebGL viewer
    if demo.file_type == 'webgl':
        return redirect('core:admin_webgl_preview', demo_id=demo.id)
    
    # ✅ For video demos, show video player
    context = {
        'demo': demo,
        'is_admin_preview': True,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demos/watch.html', context)

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_delete_demo_view(request, demo_id):
    """Delete demo - UPDATED WITH WEBGL SUPPORT"""
    demo = get_object_or_404(Demo, id=demo_id)
    demo_title = demo.title
    demo_type = demo.get_file_type_display()
    
    try:
        # Delete associated files based on file type
        if demo.video_file:
            demo.video_file.delete(save=False)
        
        if demo.webgl_file:
            demo.webgl_file.delete(save=False)
        
        if demo.thumbnail:
            demo.thumbnail.delete(save=False)
        
        # Delete demo (CASCADE will handle related objects like views, likes, requests)
        demo.delete()
        
        messages.success(request, f'{demo_type} demo "{demo_title}" has been deleted successfully.')
        return redirect('core:admin_demos')
        
    except Exception as e:
        messages.error(request, f'Error deleting demo: {str(e)}')
        return redirect('core:admin_demos')

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