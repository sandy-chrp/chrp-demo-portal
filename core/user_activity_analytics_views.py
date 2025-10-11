# core/user_activity_analytics_views.py - COMPLETE FIXED VERSION

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q
from django.db.models.functions import ExtractHour
from datetime import timedelta, datetime
import json

# Import models - FIXED
from django.contrib.auth import get_user_model
from demos.models import Demo, DemoView, DemoRequest
from enquiries.models import BusinessEnquiry

User = get_user_model()


def is_admin(user):
    """Check if user is admin/staff"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
@user_passes_test(is_admin)
def user_activity_analytics_page(request):
    """Main user activity analytics page"""
    
    # Get initial period (default: daily)
    period = request.GET.get('period', 'daily')
    
    context = {
        'activity_period': period,
        'page_title': 'User Activity Analytics',
    }
    
    return render(request, 'admin/user_activity_analytics.html', context)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def ajax_activity_analytics(request):
    """AJAX endpoint for activity analytics - FIXED VERSION"""
    
    try:
        # Get parameters
        period = request.GET.get('period', 'daily')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        # Calculate date range
        end_date = timezone.now()
        
        if period == 'daily':
            start_date = end_date - timedelta(days=7)
            date_format = '%m/%d'
            group_label = 'Last 7 Days'
        elif period == 'weekly':
            start_date = end_date - timedelta(weeks=4)
            date_format = 'Week %W'
            group_label = 'Last 4 Weeks'
        elif period == 'monthly':
            start_date = end_date - timedelta(days=180)
            date_format = '%b %Y'
            group_label = 'Last 6 Months'
        elif period == 'custom' and start_date_str and end_date_str:
            try:
                start_date = timezone.make_aware(
                    datetime.strptime(start_date_str, '%Y-%m-%d')
                )
                end_date = timezone.make_aware(
                    datetime.strptime(end_date_str, '%Y-%m-%d')
                )
                date_format = '%m/%d'
                group_label = f"{start_date_str} to {end_date_str}"
            except ValueError as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid date format: {str(e)}'
                }, status=400)
        else:
            start_date = end_date - timedelta(days=7)
            date_format = '%m/%d'
            group_label = 'Last 7 Days'
        
        # Calculate stats for current period
        period_duration = max((end_date.date() - start_date.date()).days, 1)
        previous_period_end = start_date
        previous_period_start = previous_period_end - timedelta(days=period_duration)
        
        # ===== ACTIVE USERS =====
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
        
        active_users_change = round(
            ((current_active_users - previous_active_users) / max(previous_active_users, 1)) * 100,
            1
        ) if previous_active_users > 0 else 0
        
        # ===== TOTAL VIEWS =====
        current_views = DemoView.objects.filter(
            viewed_at__range=[start_date, end_date]
        ).count()
        previous_views = DemoView.objects.filter(
            viewed_at__range=[previous_period_start, previous_period_end]
        ).count()
        views_change = round(
            ((current_views - previous_views) / max(previous_views, 1)) * 100,
            1
        ) if previous_views > 0 else 0
        
        # ===== DEMO REQUESTS =====
        current_requests = DemoRequest.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        previous_requests = DemoRequest.objects.filter(
            created_at__range=[previous_period_start, previous_period_end]
        ).count()
        requests_change = round(
            ((current_requests - previous_requests) / max(previous_requests, 1)) * 100,
            1
        ) if previous_requests > 0 else 0
        
        # ===== ENQUIRIES =====
        current_enquiries = BusinessEnquiry.objects.filter(
            created_at__range=[start_date, end_date]
        ).count()
        previous_enquiries = BusinessEnquiry.objects.filter(
            created_at__range=[previous_period_start, previous_period_end]
        ).count()
        enquiries_change = round(
            ((current_enquiries - previous_enquiries) / max(previous_enquiries, 1)) * 100,
            1
        ) if previous_enquiries > 0 else 0
        
        # ===== TIMELINE DATA =====
        timeline_data = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            date_start = timezone.make_aware(
                timezone.datetime.combine(current_date, timezone.datetime.min.time())
            )
            date_end = timezone.make_aware(
                timezone.datetime.combine(current_date, timezone.datetime.max.time())
            )
            
            views = DemoView.objects.filter(viewed_at__range=[date_start, date_end]).count()
            requests = DemoRequest.objects.filter(created_at__range=[date_start, date_end]).count()
            enquiries = BusinessEnquiry.objects.filter(created_at__range=[date_start, date_end]).count()
            logins = User.objects.filter(
                last_login__range=[date_start, date_end],
                is_staff=False,
                is_superuser=False
            ).count()
            
            timeline_data.append({
                'date': current_date.strftime(date_format),
                'views': views,
                'requests': requests,
                'enquiries': enquiries,
                'logins': logins,
            })
            
            current_date += timedelta(days=1)
        
        # ===== PEAK HOURS =====
        last_30_days = timezone.now() - timedelta(days=30)
        
        demo_view_hours = DemoView.objects.filter(
            viewed_at__gte=last_30_days
        ).annotate(hour=ExtractHour('viewed_at')).values('hour').annotate(count=Count('id'))
        
        demo_request_hours = DemoRequest.objects.filter(
            created_at__gte=last_30_days
        ).annotate(hour=ExtractHour('created_at')).values('hour').annotate(count=Count('id'))
        
        enquiry_hours = BusinessEnquiry.objects.filter(
            created_at__gte=last_30_days
        ).annotate(hour=ExtractHour('created_at')).values('hour').annotate(count=Count('id'))
        
        hour_counts = {}
        for item in demo_view_hours:
            if item['hour'] is not None:
                hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
        for item in demo_request_hours:
            if item['hour'] is not None:
                hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
        for item in enquiry_hours:
            if item['hour'] is not None:
                hour_counts[item['hour']] = hour_counts.get(item['hour'], 0) + item['count']
        
        total_activities = sum(hour_counts.values()) if hour_counts else 0
        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        peak_hours = []
        for hour, count in sorted_hours:
            try:
                start_hour = f"{int(hour):02d}:00"
                end_hour = f"{(int(hour)+1):02d}:00"
                time_slot = f"{start_hour} - {end_hour}"
                percentage = round((count / total_activities * 100), 1) if total_activities > 0 else 0
                
                peak_hours.append({
                    'time_slot': time_slot,
                    'count': count,
                    'percentage': percentage
                })
            except (ValueError, TypeError):
                continue
        
        # ===== MOST ACTIVE USERS =====
        most_active_users = User.objects.filter(
            is_staff=False,
            is_superuser=False
        ).annotate(
            activity_count=(
                Count('demo_views', filter=Q(demo_views__viewed_at__gte=last_30_days)) + 
                Count('demo_requests', filter=Q(demo_requests__created_at__gte=last_30_days)) + 
                Count('enquiries', filter=Q(enquiries__created_at__gte=last_30_days))
            )
        ).filter(activity_count__gt=0).order_by('-activity_count')[:10]
        
        active_users_list = []
        for user in most_active_users:
            active_users_list.append({
                'full_name': user.get_full_name() or user.email,
                'email': user.email,
                'organization': getattr(user, 'organization', 'N/A') or 'N/A',
                'activity_count': user.activity_count
            })
        
        # ===== RESPONSE DATA =====
        response_data = {
            'success': True,
            'period': period,
            'period_label': group_label,
            'stats': {
                'active_users': {
                    'value': current_active_users,
                    'change': active_users_change,
                    'previous': previous_active_users
                },
                'total_views': {
                    'value': current_views,
                    'change': views_change,
                    'previous': previous_views
                },
                'demo_requests': {
                    'value': current_requests,
                    'change': requests_change,
                    'previous': previous_requests
                },
                'enquiries': {
                    'value': current_enquiries,
                    'change': enquiries_change,
                    'previous': previous_enquiries
                }
            },
            'timeline': timeline_data,
            'peak_hours': peak_hours,
            'most_active_users': active_users_list,
            'date_range': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d')
            }
        }
        
        return JsonResponse(response_data)
    
    except Exception as e:
        import traceback
        print(f"Error in ajax_activity_analytics: {str(e)}")
        print(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def ajax_quick_stats(request):
    """Quick stats for dashboard widgets - lightweight"""
    
    try:
        today = timezone.now().date()
        
        today_views = DemoView.objects.filter(viewed_at__date=today).count()
        today_requests = DemoRequest.objects.filter(created_at__date=today).count()
        today_enquiries = BusinessEnquiry.objects.filter(created_at__date=today).count()
        today_signups = User.objects.filter(
            created_at__date=today,
            is_staff=False,
            is_superuser=False
        ).count()
        
        last_hour = timezone.now() - timedelta(hours=1)
        active_now = User.objects.filter(
            last_login__gte=last_hour,
            is_staff=False,
            is_superuser=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'today': {
                'views': today_views,
                'requests': today_requests,
                'enquiries': today_enquiries,
                'signups': today_signups,
                'active_now': active_now
            },
            'timestamp': timezone.now().isoformat()
        })
    
    except Exception as e:
        import traceback
        print(f"Error in ajax_quick_stats: {str(e)}")
        print(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    



@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def ajax_registration_data(request):
    """AJAX endpoint for registration chart data - NO PAGE RELOAD"""
    
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        period = request.GET.get('period', 'daily')
        start_date_str = request.GET.get('start_date')
        end_date_str = request.GET.get('end_date')
        
        today = timezone.now().date()
        end_date = timezone.now()
        
        # Determine date range
        if period == 'daily':
            start_date = end_date - timedelta(days=7)
            date_format = '%m/%d'
        elif period == 'weekly':
            start_date = end_date - timedelta(weeks=12)
            date_format = 'Week %W'
        elif period == 'monthly':
            start_date = end_date - timedelta(days=365)
            date_format = '%b %Y'
        elif period == 'custom' and start_date_str and end_date_str:
            try:
                start_date = timezone.make_aware(
                    datetime.strptime(start_date_str, '%Y-%m-%d')
                )
                end_date = timezone.make_aware(
                    datetime.strptime(end_date_str, '%Y-%m-%d')
                )
                date_format = '%m/%d'
            except ValueError as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid date format: {str(e)}'
                }, status=400)
        else:
            start_date = end_date - timedelta(days=7)
            date_format = '%m/%d'
        
        # Generate monthly users data
        monthly_users = []
        
        if period == 'monthly':
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
        elif period == 'weekly':
            # Weekly breakdown
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
        
        return JsonResponse({
            'success': True,
            'period': period,
            'monthly_users': monthly_users
        })
    
    except Exception as e:
        import traceback
        print(f"Error in ajax_registration_data: {str(e)}")
        print(traceback.format_exc())
        
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)
