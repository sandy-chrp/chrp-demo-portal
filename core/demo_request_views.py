# demo_request_views.py - Complete Demo Requests Management System with Enhanced Validation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta
import json
import pytz

# App imports
from accounts.models import BusinessCategory, BusinessSubCategory, CustomUser
from demos.models import Demo, DemoRequest, TimeSlot
from enquiries.models import BusinessEnquiry
from notifications.models import Notification, NotificationTemplate
from django.contrib.contenttypes.models import ContentType


def is_admin(user):
    """Check if user is admin"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def get_filtered_demos_for_business(business_category=None, business_subcategory=None):
    """
    Get demos filtered by business category and subcategory
    """
    demos = Demo.objects.filter(is_active=True)
    
    if business_category or business_subcategory:
        # Build the query
        query = Q()
        
        # Include demos with no restrictions (available for all)
        query |= Q(target_business_categories__isnull=True, target_business_subcategories__isnull=True)
        
        # Include demos that match the business category
        if business_category:
            query |= Q(target_business_categories=business_category)
        
        # Include demos that match the business subcategory
        if business_subcategory:
            query |= Q(target_business_subcategories=business_subcategory)
        
        demos = demos.filter(query).distinct()
    
    return demos.order_by('title')


# ================================================================================
# ADMIN DEMO REQUESTS LIST & MANAGEMENT
# ================================================================================

@login_required
@user_passes_test(is_admin)
def admin_demo_requests_list_view(request):
    """Admin demo requests management with comprehensive filtering"""
    requests_list = DemoRequest.objects.select_related(
        'user', 'demo', 'requested_time_slot', 'confirmed_time_slot', 'handled_by'
    ).order_by('-created_at')
    
    # Filtering
    status_filter = request.GET.get('status')
    demo_filter = request.GET.get('demo')
    date_filter = request.GET.get('date')
    search = request.GET.get('search')
    time_range = request.GET.get('time_range')
    sort_by = request.GET.get('sort', '-created_at')
    
    if status_filter:
        requests_list = requests_list.filter(status=status_filter)
    
    if demo_filter:
        requests_list = requests_list.filter(demo_id=demo_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            requests_list = requests_list.filter(requested_date=filter_date)
        except ValueError:
            pass
    
    if time_range:
        today = timezone.now().date()
        if time_range == 'today':
            requests_list = requests_list.filter(requested_date=today)
        elif time_range == 'tomorrow':
            tomorrow = today + timedelta(days=1)
            requests_list = requests_list.filter(requested_date=tomorrow)
        elif time_range == 'this_week':
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            requests_list = requests_list.filter(requested_date__range=[week_start, week_end])
        elif time_range == 'next_week':
            next_week_start = today + timedelta(days=7-today.weekday())
            next_week_end = next_week_start + timedelta(days=6)
            requests_list = requests_list.filter(requested_date__range=[next_week_start, next_week_end])
        elif time_range == 'this_month':
            month_start = today.replace(day=1)
            requests_list = requests_list.filter(requested_date__gte=month_start)
    
    if search:
        requests_list = requests_list.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(user__organization__icontains=search) |
            Q(demo__title__icontains=search) |
            Q(notes__icontains=search)
        )
    
    # Sorting
    if sort_by in ['-created_at', 'created_at', 'requested_date', '-requested_date', 'status', '-status']:
        requests_list = requests_list.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(requests_list, 20)
    page_number = request.GET.get('page')
    requests = paginator.get_page(page_number)
    
    # Statistics
    stats = {
        'total_requests': DemoRequest.objects.count(),
        'pending': DemoRequest.objects.filter(status='pending').count(),
        'confirmed': DemoRequest.objects.filter(status='confirmed').count(),
        'completed': DemoRequest.objects.filter(status='completed').count(),
        'cancelled': DemoRequest.objects.filter(status='cancelled').count(),
        'rescheduled': DemoRequest.objects.filter(status='rescheduled').count(),
    }
    
    # Today's and tomorrow's requests
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    today_requests = DemoRequest.objects.filter(requested_date=today).count()
    tomorrow_requests = DemoRequest.objects.filter(requested_date=tomorrow).count()
    
    # Overdue requests (pending for more than 24 hours)
    overdue_cutoff = timezone.now() - timedelta(hours=24)
    overdue_requests = DemoRequest.objects.filter(
        status='pending',
        created_at__lt=overdue_cutoff
    ).count()
    
    # Get demos for filter dropdown
    demos = Demo.objects.filter(is_active=True).order_by('title')
    
    # Context for sidebar badges
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'requests': requests,
        'demos': demos,
        'stats': stats,
        'today_requests': today_requests,
        'tomorrow_requests': tomorrow_requests,
        'overdue_requests': overdue_requests,
        
        # Filters
        'status_filter': status_filter,
        'demo_filter': demo_filter,
        'date_filter': date_filter,
        'search': search,
        'time_range': time_range,
        'sort_by': sort_by,
        
        # Sidebar context
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demo_requests/list.html', context)


# ================================================================================
# CREATE DEMO REQUEST
# ================================================================================

@login_required
@user_passes_test(is_admin)
def admin_create_demo_request_view(request):
    """Admin create demo request for any customer"""
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        demo_id = request.POST.get('demo_id')
        requested_date = request.POST.get('requested_date')
        requested_time_slot_id = request.POST.get('requested_time_slot_id')
        
        # Business Category fields
        business_category_id = request.POST.get('business_category_id', '').strip()
        business_subcategory_id = request.POST.get('business_subcategory_id', '').strip()
        
        # Location fields
        postal_code = request.POST.get('postal_code', '')
        city = request.POST.get('city', '')
        country_region = request.POST.get('country_region', '')
        
        notes = request.POST.get('notes', '')
        admin_notes = request.POST.get('admin_notes', '')
        
        try:
            # Validate user and demo
            user = get_object_or_404(CustomUser, id=user_id, is_active=True)
            demo = get_object_or_404(Demo, id=demo_id, is_active=True)
            
            # Parse and validate date
            try:
                requested_date = datetime.strptime(requested_date, '%Y-%m-%d').date()
                today = timezone.now().date()
                
                if requested_date < today:
                    messages.error(request, f'Cannot create request for past dates. Today is {today}, you selected {requested_date}')
                    return redirect('core:admin_create_demo_request')
                    
            except ValueError as e:
                messages.error(request, f'Invalid date format: {e}')
                return redirect('core:admin_create_demo_request')
            
            # Check if date is not Sunday
            if requested_date.weekday() == 6:
                messages.error(request, 'Cannot create request for Sundays')
                return redirect('core:admin_create_demo_request')
            
            # Get time slot
            time_slot = get_object_or_404(TimeSlot, id=requested_time_slot_id)
            
            # Get business category and subcategory
            business_category = None
            business_subcategory = None
            
            if business_category_id:
                try:
                    business_category = BusinessCategory.objects.get(id=business_category_id)
                except (BusinessCategory.DoesNotExist, ValueError):
                    messages.error(request, 'Invalid business category selected')
                    return redirect('core:admin_create_demo_request')

            if business_subcategory_id:
                try:
                    business_subcategory = BusinessSubCategory.objects.get(id=business_subcategory_id)
                    
                    # Validate subcategory belongs to category
                    if business_category and business_subcategory.category != business_category:
                        messages.error(request, 'Selected subcategory does not belong to the selected category')
                        return redirect('core:admin_create_demo_request')
                except (BusinessSubCategory.DoesNotExist, ValueError):
                    messages.error(request, 'Invalid business subcategory selected')
                    return redirect('core:admin_create_demo_request')
                        
            # Verify demo is available for the business category/subcategory
            if not demo.is_available_for_business(business_category, business_subcategory):
                messages.warning(request, 
                    f'Note: Demo "{demo.title}" may not be specifically targeted for the selected business category, but request has been created.'
                )
            
            # Check daily request limit for user
            from core.models import SiteSettings
            site_settings = SiteSettings.load()
            
            daily_requests = DemoRequest.objects.filter(
                user=user,
                requested_date=requested_date
            ).count()
            
            max_requests = site_settings.max_demo_requests_per_day
            if daily_requests >= max_requests:
                messages.error(
                    request, 
                    f'User already has {daily_requests} requests for {requested_date}. Maximum {max_requests} allowed per day.'
                )
                return redirect('core:admin_create_demo_request')
            
            # Create request with all fields including business categories
            demo_request = DemoRequest.objects.create(
                user=user,
                demo=demo,
                requested_date=requested_date,
                requested_time_slot=time_slot,
                business_category=business_category,
                business_subcategory=business_subcategory,
                postal_code=postal_code,
                city=city,
                country_region=country_region,
                is_international=(country_region and country_region != 'IN'),
                notes=notes,
                admin_notes=f'Created by admin: {request.user.username}\n{admin_notes}',
                handled_by=request.user
            )
            
            # Create notification for customer
            try:
                template = NotificationTemplate.objects.get(
                    notification_type='demo_request_created',
                    is_active=True
                )
                
                notification_title = template.title_template.replace('{{demo_title}}', demo.title)
                notification_message = template.message_template.replace('{{demo_title}}', demo.title)\
                    .replace('{{requested_date}}', requested_date.strftime('%B %d, %Y'))\
                    .replace('{{requested_time}}', str(time_slot))
            except NotificationTemplate.DoesNotExist:
                notification_title = f'Demo Request Created: {demo.title}'
                notification_message = f'Your demo request for "{demo.title}" on {requested_date.strftime("%B %d, %Y")} at {time_slot} has been created. We will confirm your appointment shortly.'
            
            Notification.objects.create(
                user=user,
                notification_type='demo_request_created',
                title=notification_title,
                message=notification_message,
                content_type=ContentType.objects.get_for_model(DemoRequest),
                object_id=demo_request.id
            )
            
            # Send email to customer
            send_demo_request_created_email(demo_request)
            
            # Option to auto-confirm
            auto_confirm = request.POST.get('auto_confirm')
            if auto_confirm:
                if requested_date.weekday() == 6:
                    messages.error(request, 'Cannot confirm request for Sundays')
                    demo_request.delete()
                    return redirect('core:admin_create_demo_request')
                
                demo_request.status = 'confirmed'
                demo_request.confirmed_date = requested_date
                demo_request.confirmed_time_slot = time_slot
                demo_request.save()
                
                # Send confirmation notification and email
                create_demo_confirmation_notification(demo_request)
                send_demo_confirmation_email(demo_request)
                
                messages.success(
                    request, 
                    f'Demo request created and confirmed for {user.full_name} on {requested_date}. Notification and email sent to customer.'
                )
            else:
                messages.success(
                    request, 
                    f'Demo request created for {user.full_name} on {requested_date}. Notification and email sent to customer.'
                )
            
            return redirect('core:admin_demo_request_detail', request_id=demo_request.id)
            
        except Exception as e:
            messages.error(request, f'Error creating demo request: {str(e)}')
            return redirect('core:admin_create_demo_request')
    
    # GET request - show form
    customers = CustomUser.objects.filter(
        is_active=True, 
        is_approved=True
    ).order_by('first_name', 'last_name')
    
    all_demos = Demo.objects.filter(is_active=True).prefetch_related(
        'target_business_categories', 
        'target_business_subcategories'
    ).order_by('title')
    
    # Prepare demo data for JavaScript filtering
    demos_data = []
    for demo in all_demos:
        demos_data.append({
            'id': demo.id,
            'title': demo.title,
            'demo_type': demo.get_demo_type_display(),
            'description': demo.description[:100],
            'duration': demo.formatted_duration,
            'business_categories': list(demo.target_business_categories.values_list('id', flat=True)),
            'business_subcategories': list(demo.target_business_subcategories.values_list('id', flat=True)),
            'is_for_all_categories': demo.is_for_all_business_categories,
            'is_for_all_subcategories': demo.is_for_all_business_subcategories,
        })
    
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    business_subcategories = BusinessSubCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    # Context for sidebar badges
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'customers': customers,
        'demos': all_demos,
        'demos_json': json.dumps(demos_data),
        'time_slots': time_slots,
        'business_categories': business_categories,
        'business_subcategories': business_subcategories,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demo_requests/create.html', context)


# ================================================================================
# AJAX - GET FILTERED DEMOS
# ================================================================================

@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def admin_get_filtered_demos(request):
    """AJAX endpoint to get demos filtered by business category/subcategory"""
    business_category_id = request.GET.get('category_id')
    business_subcategory_id = request.GET.get('subcategory_id')
    
    business_category = None
    business_subcategory = None
    
    if business_category_id:
        try:
            business_category = BusinessCategory.objects.get(id=business_category_id)
        except BusinessCategory.DoesNotExist:
            pass
    
    if business_subcategory_id:
        try:
            business_subcategory = BusinessSubCategory.objects.get(id=business_subcategory_id)
        except BusinessSubCategory.DoesNotExist:
            pass
    
    demos = get_filtered_demos_for_business(business_category, business_subcategory)
    
    demos_data = []
    for demo in demos:
        demos_data.append({
            'id': demo.id,
            'title': demo.title,
            'demo_type': demo.get_demo_type_display(),
            'description': demo.description[:100] + '...' if len(demo.description) > 100 else demo.description,
            'duration': demo.formatted_duration,
        })
    
    return JsonResponse({
        'success': True,
        'demos': demos_data,
        'count': len(demos_data)
    })


# ================================================================================
# EMAIL UTILITY FUNCTIONS
# ================================================================================

def send_demo_request_created_email(demo_request):
    """Send demo request creation email to customer"""
    try:
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        
        subject = f'Demo Request Received: {demo_request.demo.title}'
        
        try:
            html_message = render_to_string('emails/demo_request_created.html', {
                'demo_request': demo_request,
                'user': demo_request.user,
                'demo': demo_request.demo,
                'requested_date': demo_request.requested_date,
                'time_slot': demo_request.requested_time_slot,
            })
            message = strip_tags(html_message)
        except:
            message = f"""
Dear {demo_request.user.first_name},

Thank you for requesting a demo!

We have received your demo request with the following details:

Demo Details:
- Product: {demo_request.demo.title}
- Requested Date: {demo_request.requested_date.strftime('%B %d, %Y')}
- Requested Time: {demo_request.requested_time_slot}
- Business Category: {demo_request.business_category.name if demo_request.business_category else 'Not specified'}
- Business Subcategory: {demo_request.business_subcategory.name if demo_request.business_subcategory else 'Not specified'}
- Location: {demo_request.city}, {demo_request.country_region if demo_request.country_region else 'India'}

Your request is currently pending. We will review and confirm your appointment within 24 hours.

If you have any questions or need to make changes, please don't hesitate to contact us.

Best regards,
Demo Portal Team
CHRP India
            """
            html_message = None
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[demo_request.user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        print(f"✅ Demo request creation email sent to {demo_request.user.email}")
        
    except Exception as e:
        print(f"❌ Error sending demo request creation email: {e}")


def send_demo_confirmation_email(demo_request):
    """Send demo confirmation email to customer"""
    try:
        subject = f'Demo Confirmed: {demo_request.demo.title}'
        message = f"""
Dear {demo_request.user.first_name},

Your demo request has been confirmed!

Demo Details:
- Product: {demo_request.demo.title}
- Date: {demo_request.confirmed_date.strftime('%B %d, %Y')}
- Time: {demo_request.confirmed_time_slot}

We look forward to showcasing our solution to you.

Best regards,
Demo Portal Team
CHRP India
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[demo_request.user.email],
            fail_silently=True,
        )
        
        print(f"✅ Demo confirmation email sent to {demo_request.user.email}")
        
    except Exception as e:
        print(f"❌ Error sending confirmation email: {e}")


def send_demo_reschedule_email(demo_request, reason):
    """Send demo reschedule email to customer"""
    try:
        subject = f'Demo Rescheduled: {demo_request.demo.title}'
        message = f"""
Dear {demo_request.user.first_name},

Your demo has been rescheduled.

New Demo Details:
- Product: {demo_request.demo.title}
- New Date: {demo_request.confirmed_date.strftime('%B %d, %Y')}
- New Time: {demo_request.confirmed_time_slot}

Reason: {reason}

We apologize for any inconvenience.

Best regards,
Demo Portal Team
CHRP India
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[demo_request.user.email],
            fail_silently=True,
        )
        
        print(f"✅ Demo reschedule email sent to {demo_request.user.email}")
        
    except Exception as e:
        print(f"❌ Error sending reschedule email: {e}")


def send_demo_cancellation_email(demo_request, reason):
    """Send demo cancellation email to customer"""
    try:
        subject = f'Demo Cancelled: {demo_request.demo.title}'
        message = f"""
Dear {demo_request.user.first_name},

Unfortunately, your demo request has been cancelled.

Demo Details:
- Product: {demo_request.demo.title}
- Original Date: {demo_request.requested_date.strftime('%B %d, %Y')}
- Time: {demo_request.requested_time_slot}

Reason: {reason}

Please feel free to submit a new request or contact us directly.

Best regards,
Demo Portal Team
CHRP India
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[demo_request.user.email],
            fail_silently=True,
        )
        
        print(f"✅ Demo cancellation email sent to {demo_request.user.email}")
        
    except Exception as e:
        print(f"❌ Error sending cancellation email: {e}")


def create_demo_confirmation_notification(demo_request):
    """Create confirmation notification for demo request"""
    try:
        try:
            template = NotificationTemplate.objects.get(
                notification_type='demo_confirmation',
                is_active=True
            )
            
            notification_title = template.title_template.replace('{{demo_title}}', demo_request.demo.title)
            notification_message = template.message_template\
                .replace('{{demo_title}}', demo_request.demo.title)\
                .replace('{{confirmed_date}}', demo_request.confirmed_date.strftime('%B %d, %Y'))\
                .replace('{{confirmed_time}}', str(demo_request.confirmed_time_slot))
        except NotificationTemplate.DoesNotExist:
            notification_title = f'Demo Confirmed: {demo_request.demo.title}'
            notification_message = f'Your demo for "{demo_request.demo.title}" has been confirmed for {demo_request.confirmed_date.strftime("%B %d, %Y")} at {demo_request.confirmed_time_slot}.'
        
        Notification.objects.create(
            user=demo_request.user,
            notification_type='demo_confirmation',
            title=notification_title,
            message=notification_message,
            content_type=ContentType.objects.get_for_model(DemoRequest),
            object_id=demo_request.id
        )
        
        print(f"✅ Demo confirmation notification created for {demo_request.user.email}")
        
    except Exception as e:
        print(f"❌ Error creating confirmation notification: {e}")


# ================================================================================
# EDIT DEMO REQUEST
# ================================================================================

@login_required
@user_passes_test(is_admin)
def admin_edit_demo_request_view(request, request_id):
    """Admin edit demo request"""
    demo_request = get_object_or_404(DemoRequest, id=request_id)
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        demo_id = request.POST.get('demo_id')
        requested_date = request.POST.get('requested_date')
        requested_time_slot_id = request.POST.get('requested_time_slot_id')
        status = request.POST.get('status')
        
        business_category_id = request.POST.get('business_category_id', '').strip()
        business_subcategory_id = request.POST.get('business_subcategory_id', '').strip()
        
        postal_code = request.POST.get('postal_code', '').strip()
        city = request.POST.get('city', '').strip()
        country_region = request.POST.get('country_region', '').strip()
        
        notes = request.POST.get('notes', '')
        admin_notes = request.POST.get('admin_notes', '')
        
        try:
            if user_id:
                user = get_object_or_404(CustomUser, id=user_id, is_active=True)
                demo_request.user = user
            
            if demo_id:
                demo = get_object_or_404(Demo, id=demo_id, is_active=True)
                demo_request.demo = demo
            
            if requested_date:
                new_date = datetime.strptime(requested_date, '%Y-%m-%d').date()
                if new_date >= timezone.now().date() and new_date.weekday() != 6:
                    demo_request.requested_date = new_date
            
            if requested_time_slot_id:
                time_slot = get_object_or_404(TimeSlot, id=requested_time_slot_id)
                demo_request.requested_time_slot = time_slot
            
            business_category = None
            business_subcategory = None
            
            if business_category_id:
                try:
                    business_category = BusinessCategory.objects.get(id=business_category_id)
                except (BusinessCategory.DoesNotExist, ValueError):
                    messages.warning(request, 'Invalid business category selected')
            
            if business_subcategory_id:
                try:
                    business_subcategory = BusinessSubCategory.objects.get(id=business_subcategory_id)
                    if business_category and business_subcategory.category != business_category:
                        messages.warning(request, 'Selected subcategory does not belong to the selected category')
                        business_subcategory = None
                except (BusinessSubCategory.DoesNotExist, ValueError):
                    messages.warning(request, 'Invalid business subcategory selected')
            
            demo_request.business_category = business_category
            demo_request.business_subcategory = business_subcategory
            
            demo_request.postal_code = postal_code
            demo_request.city = city
            demo_request.country_region = country_region if country_region else None
            
            if country_region and country_region.strip():
                demo_request.is_international = (country_region != 'IN')
            else:
                demo_request.is_international = False
            
            demo_request.notes = notes
            demo_request.admin_notes = admin_notes
            demo_request.status = status
            demo_request.handled_by = request.user
            
            demo_request.save()
            
            messages.success(request, 'Demo request updated successfully')
            return redirect('core:admin_demo_request_detail', request_id=demo_request.id)
            
        except Exception as e:
            messages.error(request, f'Error updating demo request: {str(e)}')
    
    customers = CustomUser.objects.filter(is_active=True, is_approved=True).order_by('first_name', 'last_name')
    demos = Demo.objects.filter(is_active=True).order_by('title')
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('name')
    business_subcategories = BusinessSubCategory.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name')
    
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'demo_request': demo_request,
        'customers': customers,
        'demos': demos,
        'time_slots': time_slots,
        'business_categories': business_categories,
        'business_subcategories': business_subcategories,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demo_requests/edit.html', context)


# ================================================================================
# DELETE DEMO REQUEST
# ================================================================================

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_delete_demo_request_view(request, request_id):
    """Delete demo request"""
    demo_request = get_object_or_404(DemoRequest, id=request_id)
    
    try:
        if demo_request.status not in ['cancelled'] and not request.POST.get('force_delete'):
            return JsonResponse({
                'success': False,
                'error': 'Only cancelled requests can be deleted'
            })
        
        customer_name = demo_request.user.full_name
        demo_title = demo_request.demo.title
        
        demo_request.delete()
        
        messages.success(
            request,
            f'Demo request for {customer_name} - {demo_title} has been deleted'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Demo request deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ================================================================================
# DEMO REQUEST DETAIL
# ================================================================================

@login_required
@user_passes_test(is_admin)
def admin_demo_request_detail_view(request, request_id):
    """Demo request detail view with comprehensive management"""
    demo_request = get_object_or_404(DemoRequest, id=request_id)
    
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    user_other_requests = DemoRequest.objects.filter(
        user=demo_request.user
    ).exclude(id=request_id).order_by('-created_at')[:5]
    
    conflicts = []
    if demo_request.confirmed_date and demo_request.confirmed_time_slot:
        conflicts = DemoRequest.objects.filter(
            confirmed_date=demo_request.confirmed_date,
            confirmed_time_slot=demo_request.confirmed_time_slot,
            status='confirmed'
        ).exclude(id=request_id)
    
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'demo_request': demo_request,
        'time_slots': time_slots,
        'user_other_requests': user_other_requests,
        'conflicts': conflicts,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demo_requests/detail.html', context)


# ================================================================================
# CONFIRM/RESCHEDULE/CANCEL DEMO REQUEST - WITH ENHANCED VALIDATION
# ================================================================================

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_confirm_demo_request_view(request, request_id):
    """
    Confirm demo request with date and time - WITH ENHANCED VALIDATION
    ✅ Same validation logic as customer side
    """
    demo_request = get_object_or_404(DemoRequest, id=request_id)
    
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        action = data.get('action')
        
        if action == 'confirm':
            confirmed_date_str = data.get('confirmed_date')
            confirmed_time_slot_id = data.get('confirmed_time_slot_id')
            admin_notes = data.get('admin_notes', '')
            
            if not confirmed_date_str or not confirmed_time_slot_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Date and time slot are required'
                })
            
            # Parse date
            confirmed_date = datetime.strptime(confirmed_date_str, '%Y-%m-%d').date()
            
            # Get time slot
            confirmed_time_slot = get_object_or_404(TimeSlot, id=confirmed_time_slot_id)
            
            # ✅ VALIDATION LOGIC - Same as customer side
            indian_tz = pytz.timezone('Asia/Kolkata')
            now_utc = timezone.now()
            now_indian = now_utc.astimezone(indian_tz)
            
            today = now_indian.date()
            current_time = now_indian.time()
            
            print(f"\n{'='*60}")
            print(f"🔍 ADMIN BOOKING VALIDATION")
            print(f"{'='*60}")
            print(f"📅 Confirmed Date: {confirmed_date}")
            print(f"⏰ Time Slot: {confirmed_time_slot.start_time} - {confirmed_time_slot.end_time}")
            print(f"🇮🇳 Current Indian Time: {now_indian}")
            print(f"📆 Today's Date: {today}")
            print(f"🕐 Current Time: {current_time}")
            print(f"👤 Admin: {request.user.username}")
            print(f"{'='*60}\n")
            
            # ✅ VALIDATION 0: Check if date is in the past
            if confirmed_date < today:
                print(f"❌ VALIDATION FAILED: Past date")
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot confirm demo for past dates'
                })
            
            # ✅ VALIDATION 1: Check if date is Sunday
            if confirmed_date.weekday() == 6:
                print(f"❌ VALIDATION FAILED: Sunday selected")
                return JsonResponse({
                    'success': False,
                    'error': 'Demos cannot be scheduled on Sundays'
                })
            
            # ✅ VALIDATION 2: Check if requested time slot has ENDED (for today)
            if confirmed_date == today:
                # Check if slot has ENDED (current time >= END time)
                if current_time >= confirmed_time_slot.end_time:
                    print(f"❌ VALIDATION FAILED: Slot has ended")
                    print(f"   Slot ends at: {confirmed_time_slot.end_time}")
                    print(f"   Current time: {current_time}")
                    
                    return JsonResponse({
                        'success': False,
                        'error': f'The time slot {confirmed_time_slot.start_time.strftime("%I:%M %p")} - '
                                f'{confirmed_time_slot.end_time.strftime("%I:%M %p")} has already ended '
                                f'(Current time: {current_time.strftime("%I:%M %p")}). '
                                f'Please select a future time slot.'
                    })
                
                # Check if slot is starting within 30 minutes (but hasn't started yet)
                slot_start_datetime = indian_tz.localize(
                    datetime.combine(confirmed_date, confirmed_time_slot.start_time)
                )
                current_datetime = now_indian
                
                time_until_start = (slot_start_datetime - current_datetime).total_seconds() / 60
                
                print(f"\n🔍 STARTING SOON CHECK:")
                print(f"   Slot start: {slot_start_datetime}")
                print(f"   Current: {current_datetime}")
                print(f"   Time until start: {time_until_start:.2f} minutes")
                
                # Only block if starting within 30 minutes AND hasn't started yet
                if 0 < time_until_start < 30:
                    print(f"❌ VALIDATION FAILED: Slot starting within 30 minutes ({time_until_start:.2f} min)")
                    return JsonResponse({
                        'success': False,
                        'error': f'Cannot confirm slots starting within 30 minutes. '
                                f'The slot at {confirmed_time_slot.start_time.strftime("%I:%M %p")} '
                                f'is starting in {int(time_until_start)} minutes. '
                                f'Please select a slot starting at least 30 minutes from now.'
                    })
                elif time_until_start <= 0:
                    # Slot has already started - check if it hasn't ended
                    if current_time < confirmed_time_slot.end_time:
                        # Slot is in progress - ALLOW CONFIRMATION!
                        print(f"✅ Slot in progress but still confirmable (ends at {confirmed_time_slot.end_time})")
                    else:
                        print(f"❌ Slot has ended")
                        return JsonResponse({
                            'success': False,
                            'error': 'The time slot has already ended. Please select a future time slot.'
                        })
                else:
                    print(f"✅ STARTING SOON CHECK PASSED: {time_until_start:.2f} minutes until start")
            
            # ✅ VALIDATION 3: Check for conflicts
            conflicts = DemoRequest.objects.filter(
                confirmed_date=confirmed_date,
                confirmed_time_slot=confirmed_time_slot,
                status='confirmed'
            ).exclude(id=request_id)
            
            if conflicts.exists():
                print(f"❌ VALIDATION FAILED: Time slot conflict")
                return JsonResponse({
                    'success': False,
                    'error': f'Time slot conflict: Another demo is already scheduled at this time'
                })
            
            # ✅ All validations passed
            print(f"\n{'='*60}")
            print(f"✅ ALL VALIDATIONS PASSED - CONFIRMING BOOKING")
            print(f"{'='*60}\n")
            
            # Update request
            demo_request.status = 'confirmed'
            demo_request.confirmed_date = confirmed_date
            demo_request.confirmed_time_slot = confirmed_time_slot
            demo_request.admin_notes = admin_notes
            demo_request.handled_by = request.user
            demo_request.save()
            
            # Send confirmation email
            send_demo_confirmation_email(demo_request)
            
            # Create notification
            create_demo_confirmation_notification(demo_request)
            
            messages.success(
                request, 
                f'Demo request confirmed for {confirmed_date} at {confirmed_time_slot}'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Demo request confirmed successfully',
                'status': 'confirmed'
            })
            
        elif action == 'reschedule':
            # Similar validation for reschedule
            new_date_str = data.get('new_date')
            new_time_slot_id = data.get('new_time_slot_id')
            reason = data.get('reason', '')
            
            if not new_date_str or not new_time_slot_id:
                return JsonResponse({
                    'success': False,
                    'error': 'New date and time slot are required'
                })
            
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            new_time_slot = get_object_or_404(TimeSlot, id=new_time_slot_id)
            
            # Apply same validation logic as confirm
            indian_tz = pytz.timezone('Asia/Kolkata')
            now_utc = timezone.now()
            now_indian = now_utc.astimezone(indian_tz)
            
            today = now_indian.date()
            current_time = now_indian.time()
            
            # Check constraints
            if new_date < today:
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot reschedule to past dates'
                })
            
            if new_date.weekday() == 6:
                return JsonResponse({
                    'success': False,
                    'error': 'Demos cannot be scheduled on Sundays'
                })
            
            # Check if slot has ended (for today)
            if new_date == today:
                if current_time >= new_time_slot.end_time:
                    return JsonResponse({
                        'success': False,
                        'error': f'The time slot has already ended. Please select a future time slot.'
                    })
                
                # Check starting soon
                slot_start_datetime = indian_tz.localize(
                    datetime.combine(new_date, new_time_slot.start_time)
                )
                current_datetime = now_indian
                time_until_start = (slot_start_datetime - current_datetime).total_seconds() / 60
                
                if 0 < time_until_start < 30:
                    return JsonResponse({
                        'success': False,
                        'error': 'Cannot reschedule to slots starting within 30 minutes'
                    })
            
            # Check conflicts
            conflicts = DemoRequest.objects.filter(
                confirmed_date=new_date,
                confirmed_time_slot=new_time_slot,
                status='confirmed'
            ).exclude(id=request_id)
            
            if conflicts.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Time slot conflict with another demo'
                })
            
            # Update request
            demo_request.status = 'rescheduled'
            demo_request.confirmed_date = new_date
            demo_request.confirmed_time_slot = new_time_slot
            demo_request.admin_notes = f"Rescheduled: {reason}\n{demo_request.admin_notes}"
            demo_request.handled_by = request.user
            demo_request.save()
            
            # Send reschedule email
            send_demo_reschedule_email(demo_request, reason)
            
            messages.success(
                request,
                f'Demo rescheduled to {new_date} at {new_time_slot}'
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Demo rescheduled successfully'
            })
            
        elif action == 'cancel':
            cancel_reason = data.get('cancel_reason', '')
            
            demo_request.status = 'cancelled'
            demo_request.admin_notes = f"Cancelled: {cancel_reason}\n{demo_request.admin_notes}"
            demo_request.handled_by = request.user
            demo_request.save()
            
            # Send cancellation email
            send_demo_cancellation_email(demo_request, cancel_reason)
            
            messages.success(request, 'Demo request cancelled')
            
            return JsonResponse({
                'success': True,
                'message': 'Demo request cancelled successfully'
            })
            
        elif action == 'complete':
            completion_notes = data.get('completion_notes', '')
            
            demo_request.status = 'completed'
            demo_request.admin_notes = f"Completed: {completion_notes}\n{demo_request.admin_notes}"
            demo_request.handled_by = request.user
            demo_request.save()
            
            messages.success(request, 'Demo marked as completed')
            
            return JsonResponse({
                'success': True,
                'message': 'Demo marked as completed'
            })
        
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid action'
            })
            
    except Exception as e:
        print(f"❌ ERROR in admin_confirm_demo_request_view: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ================================================================================
# BULK ACTIONS
# ================================================================================

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_bulk_demo_request_actions_view(request):
    """Handle bulk actions on demo requests"""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        request_ids = data.get('request_ids', [])
        
        if not request_ids:
            return JsonResponse({
                'success': False,
                'error': 'No requests selected'
            })
        
        requests_queryset = DemoRequest.objects.filter(id__in=request_ids)
        
        if action == 'bulk_cancel':
            cancel_reason = data.get('cancel_reason', 'Bulk cancellation by admin')
            
            updated_count = requests_queryset.update(
                status='cancelled',
                admin_notes=f'Cancelled: {cancel_reason}',
                handled_by=request.user
            )
            
            # Send bulk cancellation emails
            for req in requests_queryset:
                send_demo_cancellation_email(req, cancel_reason)
            
            messages.success(
                request,
                f'{updated_count} demo requests have been cancelled'
            )
            
        elif action == 'bulk_complete':
            completion_notes = data.get('completion_notes', 'Bulk completion by admin')
            
            # Only complete confirmed requests
            confirmed_requests = requests_queryset.filter(status='confirmed')
            updated_count = confirmed_requests.update(
                status='completed',
                admin_notes=f'Completed: {completion_notes}',
                handled_by=request.user
            )
            
            messages.success(
                request,
                f'{updated_count} demo requests have been marked as completed'
            )
            
        elif action == 'bulk_delete':
            # Only allow deletion of cancelled requests
            cancelled_requests = requests_queryset.filter(status='cancelled')
            deleted_count = cancelled_requests.count()
            cancelled_requests.delete()
            
            messages.success(
                request,
                f'{deleted_count} cancelled demo requests have been deleted'
            )
            
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid bulk action'
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Bulk action "{action}" completed successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ================================================================================
# CALENDAR VIEW
# ================================================================================

@login_required
@user_passes_test(is_admin)
def admin_demo_requests_calendar_view(request):
    """Calendar view of demo requests"""
    # Get current month or specified month
    month = request.GET.get('month')
    year = request.GET.get('year')
    
    if month and year:
        try:
            current_date = datetime(int(year), int(month), 1).date()
        except ValueError:
            current_date = timezone.now().date().replace(day=1)
    else:
        current_date = timezone.now().date().replace(day=1)
    
    # Calculate month range
    next_month = current_date.replace(day=28) + timedelta(days=4)
    month_end = next_month - timedelta(days=next_month.day)
    
    # Get requests for the month
    month_requests = DemoRequest.objects.filter(
        requested_date__gte=current_date,
        requested_date__lte=month_end
    ).select_related('user', 'demo', 'requested_time_slot')
    
    # Group by date
    requests_by_date = {}
    for req in month_requests:
        date_key = req.requested_date.strftime('%Y-%m-%d')
        if date_key not in requests_by_date:
            requests_by_date[date_key] = []
        requests_by_date[date_key].append(req)
    
    # Context for sidebar badges
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'current_date': current_date,
        'requests_by_date': requests_by_date,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demo_requests/calendar.html', context)


# ================================================================================
# AJAX - ADMIN CHECK SLOT AVAILABILITY
# ================================================================================

@login_required
@user_passes_test(is_admin)
@require_http_methods(["GET"])
def ajax_admin_check_slot_availability(request):
    """
    AJAX endpoint for admin to check time slot availability
    ✅ Fixed: Slot in progress logic
    """
    try:
        requested_date = request.GET.get('date')
        
        if not requested_date:
            return JsonResponse({'success': False, 'error': 'Date is required'}, status=400)
        
        try:
            check_date = datetime.strptime(requested_date, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid date format'}, status=400)
        
        # Check if Sunday
        if check_date.weekday() == 6:
            return JsonResponse({
                'success': False,
                'available': False,
                'reason': 'sunday',
                'message': 'Demo sessions are not available on Sundays'
            })
        
        indian_tz = pytz.timezone('Asia/Kolkata')
        now_utc = timezone.now()
        now_indian = now_utc.astimezone(indian_tz)
        
        today = now_indian.date()
        current_time = now_indian.time()
        
        print(f"🕐 Admin checking slots for: {check_date}")
        print(f"🇮🇳 Current Indian time: {now_indian}")
        
        # Check if past date
        if check_date < today:
            return JsonResponse({
                'success': False,
                'available': False,
                'reason': 'past',
                'message': 'Cannot confirm demos for past dates'
            })
        
        # Get all active time slots
        all_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
        
        if not all_slots.exists():
            return JsonResponse({'success': False, 'message': 'No time slots configured'})
        
        # Get all confirmed bookings for this date
        confirmed_bookings = DemoRequest.objects.filter(
            Q(confirmed_date=check_date) | 
            Q(requested_date=check_date, confirmed_date__isnull=True),
            status__in=['pending', 'confirmed']
        ).select_related('demo', 'user', 'confirmed_time_slot', 'requested_time_slot')
        
        slots_data = []
        max_bookings_per_slot = 1
        is_today = check_date == today
        
        for slot in all_slots:
            is_past_slot = False
            is_starting_soon = False
            
            if is_today:
                # ✅ FIXED: Check if slot has ENDED (current time >= end time)
                if current_time >= slot.end_time:
                    is_past_slot = True
                    print(f"⏰ Slot {slot.start_time}-{slot.end_time} - ENDED (current: {current_time})")
                else:
                    # Slot hasn't ended - check if it's starting soon
                    slot_start_datetime = indian_tz.localize(
                        datetime.combine(check_date, slot.start_time)
                    )
                    current_datetime = now_indian
                    time_until_start = (slot_start_datetime - current_datetime).total_seconds() / 60
                    
                    # Check if starting within 30 minutes
                    if 0 < time_until_start < 30:
                        is_starting_soon = True
                        is_past_slot = True  # Block booking
                        print(f"   ⚠️ Starting soon ({time_until_start:.2f} min) - BLOCKED")
                    elif time_until_start <= 0:
                        # Slot has already started but not ended
                        minutes_since_start = abs(time_until_start)
                        print(f"   ✅ Slot in progress (started {minutes_since_start:.2f} min ago) - BOOKABLE")
                    else:
                        print(f"   ✅ Future slot: {time_until_start:.2f} minutes until start - BOOKABLE")
            
            # Get bookings for this slot
            slot_bookings = confirmed_bookings.filter(
                Q(confirmed_time_slot=slot) | 
                Q(requested_time_slot=slot, confirmed_time_slot__isnull=True)
            )
            
            confirmed_count = slot_bookings.count()
            available_spots = max_bookings_per_slot - confirmed_count
            
            # Determine status
            if is_past_slot and not is_starting_soon:
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
            
            # Get booking details for admin
            booking_details = []
            for booking in slot_bookings:
                booking_details.append({
                    'id': booking.id,
                    'customer_name': booking.user.full_name,
                    'customer_email': booking.user.email,
                    'demo_title': booking.demo.title,
                    'status': booking.get_status_display(),
                })
            
            slot_info = {
                'id': slot.id,
                'start_time': slot.start_time.strftime('%I:%M %p'),
                'end_time': slot.end_time.strftime('%I:%M %p'),
                'slot_type': slot.get_slot_type_display(),
                'is_available': is_available,
                'confirmed_bookings': confirmed_count,
                'available_spots': max(0, available_spots),
                'total_capacity': max_bookings_per_slot,
                'status': status,
                'status_message': status_message,
                'is_past': is_past_slot,
                'is_starting_soon': is_starting_soon,
                'booking_details': booking_details,
            }
            
            slots_data.append(slot_info)
        
        return JsonResponse({
            'success': True,
            'available': True,
            'date': requested_date,
            'day_name': check_date.strftime('%A'),
            'is_today': is_today,
            'slots': slots_data,
            'total_bookings': confirmed_bookings.count(),
            'message': f'{confirmed_bookings.count()} demos scheduled for {check_date.strftime("%B %d, %Y")}'
        })
        
    except Exception as e:
        print(f"❌ Error in ajax_admin_check_slot_availability: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': 'Server error occurred',
            'details': str(e)
        }, status=500)