# demo_request_views.py - Complete Demo Requests Management System
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
from accounts.models import BusinessCategory, BusinessSubCategory
from demos.models import Demo, DemoRequest, TimeSlot
from accounts.models import CustomUser
from enquiries.models import BusinessEnquiry

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
            
            if business_category_id:  # Only if not empty string
                try:
                    from accounts.models import BusinessCategory
                    business_category = BusinessCategory.objects.get(id=business_category_id)
                except (BusinessCategory.DoesNotExist, ValueError):
                    messages.error(request, 'Invalid business category selected')
                    return redirect('core:admin_create_demo_request')

            if business_subcategory_id:  # Only if not empty string
                try:
                    from accounts.models import BusinessSubCategory
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
                business_category=business_category,  # This will be None if empty, which is correct
                business_subcategory=business_subcategory,  # This will be None if empty, which is correct
                postal_code=postal_code,
                city=city,
                country_region=country_region,
                is_international=(country_region and country_region != 'IN'),
                notes=notes,
                admin_notes=f'Created by admin: {request.user.username}\n{admin_notes}',
                handled_by=request.user
            )
            
            # Create notification for customer
            from notifications.models import Notification, NotificationTemplate
            from django.contrib.contenttypes.models import ContentType
            
            # Try to get template for demo request creation
            try:
                template = NotificationTemplate.objects.get(
                    notification_type='demo_request_created',
                    is_active=True
                )
                
                # Format the notification message
                notification_title = template.title_template.replace('{{demo_title}}', demo.title)
                notification_message = template.message_template.replace('{{demo_title}}', demo.title)\
                    .replace('{{requested_date}}', requested_date.strftime('%B %d, %Y'))\
                    .replace('{{requested_time}}', str(time_slot))
            except NotificationTemplate.DoesNotExist:
                # Use default messages if template doesn't exist
                notification_title = f'Demo Request Created: {demo.title}'
                notification_message = f'Your demo request for "{demo.title}" on {requested_date.strftime("%B %d, %Y")} at {time_slot} has been created. We will confirm your appointment shortly.'
            
            # Create the notification
            notification = Notification.objects.create(
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
    # Get active customers
    customers = CustomUser.objects.filter(
        is_active=True, 
        is_approved=True
    ).order_by('first_name', 'last_name')
    
    # Get all active demos initially (will be filtered by JS based on selection)
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
            'demo_type': demo.get_demo_type_display(),  # ✅ Use demo_type instead
            'description': demo.description[:100],
            'duration': demo.formatted_duration,
            'business_categories': list(demo.target_business_categories.values_list('id', flat=True)),
            'business_subcategories': list(demo.target_business_subcategories.values_list('id', flat=True)),
            'is_for_all_categories': demo.is_for_all_business_categories,
            'is_for_all_subcategories': demo.is_for_all_business_subcategories,
        })
    
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    # Get business categories and subcategories
    from accounts.models import BusinessCategory, BusinessSubCategory
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    business_subcategories = BusinessSubCategory.objects.filter(is_active=True).order_by('sort_order', 'name')
    
    # Context for sidebar badges
    from enquiries.models import BusinessEnquiry
    pending_approvals = CustomUser.objects.filter(is_approved=False, is_active=True).count()
    open_enquiries = BusinessEnquiry.objects.filter(status='open').count()
    demo_requests_pending = DemoRequest.objects.filter(status='pending').count()
    
    context = {
        'customers': customers,
        'demos': all_demos,
        'demos_json': json.dumps(demos_data),  # For JavaScript filtering
        'time_slots': time_slots,
        'business_categories': business_categories,
        'business_subcategories': business_subcategories,
        'pending_approvals': pending_approvals,
        'open_enquiries': open_enquiries,
        'demo_requests_pending': demo_requests_pending,
    }
    
    return render(request, 'admin/demo_requests/create.html', context)


# AJAX endpoint to get filtered demos
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
        from accounts.models import BusinessCategory
        try:
            business_category = BusinessCategory.objects.get(id=business_category_id)
        except BusinessCategory.DoesNotExist:
            pass
    
    if business_subcategory_id:
        from accounts.models import BusinessSubCategory
        try:
            business_subcategory = BusinessSubCategory.objects.get(id=business_subcategory_id)
        except BusinessSubCategory.DoesNotExist:
            pass
    
    # Get filtered demos
    demos = get_filtered_demos_for_business(business_category, business_subcategory)
    
    # Prepare response data
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

# New email function for demo request creation
def send_demo_request_created_email(demo_request):
    """Send demo request creation email to customer"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        
        subject = f'Demo Request Received: {demo_request.demo.title}'
        
        # Try to render HTML template if exists
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
            # Fallback to plain text
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
        
        # Log email sent
        print(f"Demo request creation email sent to {demo_request.user.email}")
        
    except Exception as e:
        print(f"Error sending demo request creation email: {e}")

def create_demo_confirmation_notification(demo_request):
    """Create confirmation notification for demo request"""
    try:
        from notifications.models import Notification, NotificationTemplate
        from django.contrib.contenttypes.models import ContentType
        
        # Try to get template
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
        
    except Exception as e:
        print(f"Error creating confirmation notification: {e}")

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
        
        # Business category fields - handle empty strings
        business_category_id = request.POST.get('business_category_id', '').strip()
        business_subcategory_id = request.POST.get('business_subcategory_id', '').strip()
        
        # Location fields
        postal_code = request.POST.get('postal_code', '').strip()
        city = request.POST.get('city', '').strip()
        country_region = request.POST.get('country_region', '').strip()
        
        # Notes
        notes = request.POST.get('notes', '')
        admin_notes = request.POST.get('admin_notes', '')
        
        try:
            # Update user if changed
            if user_id:
                user = get_object_or_404(CustomUser, id=user_id, is_active=True)
                demo_request.user = user
            
            # Update demo
            if demo_id:
                demo = get_object_or_404(Demo, id=demo_id, is_active=True)
                demo_request.demo = demo
            
            # Update date
            if requested_date:
                new_date = datetime.strptime(requested_date, '%Y-%m-%d').date()
                if new_date >= timezone.now().date() and new_date.weekday() != 6:
                    demo_request.requested_date = new_date
            
            # Update time slot
            if requested_time_slot_id:
                time_slot = get_object_or_404(TimeSlot, id=requested_time_slot_id)
                demo_request.requested_time_slot = time_slot
            
            # Update business category - convert empty string to None
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
            
            # Update location - FIX HERE
            demo_request.postal_code = postal_code
            demo_request.city = city
            demo_request.country_region = country_region if country_region else None
            
            # Fix is_international - convert to proper boolean
            if country_region and country_region.strip():
                demo_request.is_international = (country_region != 'IN')
            else:
                demo_request.is_international = False  # Default to False if no country
            
            # Update other fields
            demo_request.notes = notes
            demo_request.admin_notes = admin_notes
            demo_request.status = status
            demo_request.handled_by = request.user
            
            demo_request.save()
            
            messages.success(request, 'Demo request updated successfully')
            return redirect('core:admin_demo_request_detail', request_id=demo_request.id)
            
        except Exception as e:
            messages.error(request, f'Error updating demo request: {str(e)}')
    
    # GET request - show form
    customers = CustomUser.objects.filter(is_active=True, is_approved=True).order_by('first_name', 'last_name')
    demos = Demo.objects.filter(is_active=True).order_by('title')
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    # Get business categories and subcategories
    business_categories = BusinessCategory.objects.filter(is_active=True).order_by('name')
    business_subcategories = BusinessSubCategory.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name')
    
    # Context for sidebar badges
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

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_delete_demo_request_view(request, request_id):
    """Delete demo request"""
    demo_request = get_object_or_404(DemoRequest, id=request_id)
    
    try:
        # Only allow deletion of cancelled requests or with confirmation
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

@login_required
@user_passes_test(is_admin)
def admin_demo_request_detail_view(request, request_id):
    """Demo request detail view with comprehensive management"""
    demo_request = get_object_or_404(DemoRequest, id=request_id)
    
    # Get available time slots
    time_slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')
    
    # Get user's other requests
    user_other_requests = DemoRequest.objects.filter(
        user=demo_request.user
    ).exclude(id=request_id).order_by('-created_at')[:5]
    
    # Check for scheduling conflicts if confirmed
    conflicts = []
    if demo_request.confirmed_date and demo_request.confirmed_time_slot:
        conflicts = DemoRequest.objects.filter(
            confirmed_date=demo_request.confirmed_date,
            confirmed_time_slot=demo_request.confirmed_time_slot,
            status='confirmed'
        ).exclude(id=request_id)
    
    # Context for sidebar badges
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

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_confirm_demo_request_view(request, request_id):
    """Confirm demo request with date and time"""
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
            
            # Check if date is not in past
            if confirmed_date < timezone.now().date():
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot confirm demo for past dates'
                })
            
            # Check if date is not Sunday
            if confirmed_date.weekday() == 6:
                return JsonResponse({
                    'success': False,
                    'error': 'Demos cannot be scheduled on Sundays'
                })
            
            # Get time slot
            confirmed_time_slot = get_object_or_404(TimeSlot, id=confirmed_time_slot_id)
            
            # Check for conflicts
            conflicts = DemoRequest.objects.filter(
                confirmed_date=confirmed_date,
                confirmed_time_slot=confirmed_time_slot,
                status='confirmed'
            ).exclude(id=request_id)
            
            if conflicts.exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Time slot conflict: Another demo is already scheduled at this time'
                })
            
            # Update request
            demo_request.status = 'confirmed'
            demo_request.confirmed_date = confirmed_date
            demo_request.confirmed_time_slot = confirmed_time_slot
            demo_request.admin_notes = admin_notes
            demo_request.handled_by = request.user
            demo_request.save()
            
            # Send confirmation email
            send_demo_confirmation_email(demo_request)
            
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
            
            # Check constraints
            if new_date < timezone.now().date():
                return JsonResponse({
                    'success': False,
                    'error': 'Cannot reschedule to past dates'
                })
            
            if new_date.weekday() == 6:
                return JsonResponse({
                    'success': False,
                    'error': 'Demos cannot be scheduled on Sundays'
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
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

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

# Email utility functions
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
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[demo_request.user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Error sending confirmation email: {e}")

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
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[demo_request.user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Error sending reschedule email: {e}")

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
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[demo_request.user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"Error sending cancellation email: {e}")