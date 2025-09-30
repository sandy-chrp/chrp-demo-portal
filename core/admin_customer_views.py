# core/admin_customer_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from datetime import datetime
import json
import uuid
import csv

from .customer_admin_forms import CustomerCreateForm, CustomerEditForm

User = get_user_model()

def is_admin(user):
    """Check if user is admin/staff"""
    return user.is_authenticated and user.is_staff

@login_required
@user_passes_test(is_admin)
def admin_customers_list(request):
    """Admin view for listing all customers"""
    # Get filter parameters
    search = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '')
    
    # Base queryset
    customers = User.objects.filter(is_staff=False).select_related()
    
    # Apply search filter
    if search:
        customers = customers.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(organization__icontains=search) |
            Q(job_title__icontains=search) |
            Q(mobile__icontains=search)
        )
    
    # Apply status filter
    if status_filter == 'active':
        customers = customers.filter(is_approved=True, is_active=True)
    elif status_filter == 'pending':
        customers = customers.filter(is_approved=False)
    elif status_filter == 'blocked':
        customers = customers.filter(is_active=False)
    
    # Get statistics
    total_customers = User.objects.filter(is_staff=False).count()
    active_customers = User.objects.filter(is_staff=False, is_approved=True, is_active=True).count()
    pending_approvals = User.objects.filter(is_staff=False, is_approved=False).count()
    blocked_customers = User.objects.filter(is_staff=False, is_active=False).count()
    
    # Pagination
    paginator = Paginator(customers.order_by('-created_at'), 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'users': page_obj,
        'search': search,
        'status_filter': status_filter,
        'total_customers': total_customers,
        'active_customers': active_customers,
        'pending_approvals': pending_approvals,
        'blocked_customers': blocked_customers,
    }
    
    return render(request, 'admin/customers/list.html', context)

@login_required
@user_passes_test(is_admin)
def admin_create_customer(request):
    """Admin view for creating new customer"""
    if request.method == 'POST':
        form = CustomerCreateForm(request.POST)
        if form.is_valid():
            try:
                # Create customer
                customer = form.save(commit=False)
                customer.is_email_verified = True
                customer.is_approved = form.cleaned_data.get('is_approved', True)
                customer.is_active = True
                customer.save()
                
                # Send welcome email if enabled
                email_sent = False
                if form.cleaned_data.get('send_welcome_email', False):
                    result = send_customer_welcome_email_with_validation(customer, request.user)
                    if result['success']:
                        email_sent = True
                        messages.success(request, f'Customer created! Welcome email sent to {customer.email}')
                    else:
                        if result['error'] == 'invalid_recipient':
                            messages.warning(
                                request,
                                f'Customer created but email "{customer.email}" does not exist or cannot receive emails. '
                                f'Please verify the email address.'
                            )
                        else:
                            messages.warning(
                                request,
                                f'Customer created but welcome email failed to send. '
                                f'You may need to contact them manually.'
                            )
                
                if not email_sent:
                    messages.success(request, f'Customer "{customer.full_name}" created successfully!')
                
                return redirect('core:admin_users')
                    
            except Exception as e:
                messages.error(request, f'Error creating customer: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerCreateForm()
    
    return render(request, 'admin/customers/create.html', {
        'form': form,
        'title': 'Create New Customer'
    })

def send_customer_welcome_email_with_validation(customer, created_by):
    """Send welcome email with delivery validation"""
    from django.core.mail import EmailMessage
    from smtplib import SMTPException
    
    try:
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        subject = 'Welcome to Demo Portal'
        message = f"""
Dear {customer.first_name} {customer.last_name},

Welcome to Demo Portal!

Your account has been created by our admin team.

Account Details:
- Email: {customer.email}
- Organization: {customer.organization}
- Job Title: {customer.job_title}

Sign in here: {site_url}/auth/signin/

Use the "Forgot Password" option to set your password.

Best regards,
Demo Portal Team
CHRP India
        """
        
        email_msg = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer.email],
        )
        email_msg.send(fail_silently=False)
        
        return {'success': True, 'error': None}
    
    except SMTPException as e:
        error_msg = str(e)
        print(f"SMTP Error sending welcome email: {error_msg}")
        
        if "550" in error_msg or "recipient" in error_msg.lower():
            return {'success': False, 'error': 'invalid_recipient'}
        elif "authentication" in error_msg.lower():
            return {'success': False, 'error': 'auth_failed'}
        else:
            return {'success': False, 'error': 'smtp_error'}
    
    except Exception as e:
        print(f"General email error: {e}")
        return {'success': False, 'error': 'unknown'}



@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def send_email_otp(request):
    """Send OTP to email for verification"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        
        if not email:
            return JsonResponse({'success': False, 'message': 'Email is required'})
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'message': 'Email already registered'})
        
        # Generate OTP
        from accounts.models import EmailOTP  # or wherever you put it
        otp_code = EmailOTP.generate_otp()
        
        # Delete old OTPs for this email
        EmailOTP.objects.filter(email=email, verified=False).delete()
        
        # Create new OTP
        otp_obj = EmailOTP.objects.create(
            email=email,
            otp=otp_code
        )
        
        # Send email
        subject = 'Email Verification OTP - Demo Portal'
        message = f"""
Dear User,

Your OTP for email verification is: {otp_code}

This OTP will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
Demo Portal Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        
        return JsonResponse({
            'success': True,
            'message': f'OTP sent to {email}',
            'expires_in': 600  # 10 minutes
        })
        
    except Exception as e:
        print(f"Error sending OTP: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Failed to send OTP. Please try again.'
        })


@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def verify_email_otp(request):
    """Verify OTP"""
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        otp_entered = data.get('otp', '').strip()
        
        if not email or not otp_entered:
            return JsonResponse({'success': False, 'message': 'Email and OTP required'})
        
        from accounts.models import EmailOTP
        
        # Get latest OTP for this email
        otp_obj = EmailOTP.objects.filter(email=email, verified=False).order_by('-created_at').first()
        
        if not otp_obj:
            return JsonResponse({'success': False, 'message': 'No OTP found. Please request new OTP.'})
        
        if not otp_obj.is_valid():
            return JsonResponse({'success': False, 'message': 'OTP expired. Please request new OTP.'})
        
        if otp_obj.otp != otp_entered:
            return JsonResponse({'success': False, 'message': 'Invalid OTP. Please try again.'})
        
        # Mark as verified
        otp_obj.verified = True
        otp_obj.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Email verified successfully!'
        })
        
    except Exception as e:
        print(f"Error verifying OTP: {e}")
        return JsonResponse({
            'success': False,
            'message': 'Verification failed. Please try again.'
        })

@login_required
@user_passes_test(is_admin)
def admin_edit_customer(request, customer_id):
    """Admin view for editing existing customer"""
    customer = get_object_or_404(User, id=customer_id, is_staff=False)
    
    if request.method == 'POST':
        form = CustomerEditForm(request.POST, instance=customer)
        if form.is_valid():
            try:
                # Save changes
                old_email = customer.email
                old_status = (customer.is_approved, customer.is_active)
                
                customer = form.save()
                
                # Check for email change
                if old_email != customer.email:
                    customer.is_email_verified = False
                    customer.email_verification_token = str(uuid.uuid4())
                    customer.save()
                    messages.info(request, 'Email changed. Customer will need to verify their new email.')
                
                # Check for status change
                new_status = (customer.is_approved, customer.is_active)
                if old_status != new_status:
                    send_status_change_notification(customer, old_status, new_status)
                
                messages.success(request, f'Customer "{customer.full_name}" updated successfully!')
                
                # Redirect based on action
                if 'save_and_continue' in request.POST:
                    return redirect('core:admin_edit_customer', customer.id)
                else:
                    return redirect('core:admin_users')
                    
            except Exception as e:
                messages.error(request, f'Error updating customer: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerEditForm(instance=customer)
    
    # Get customer statistics
    customer_stats = get_customer_statistics(customer)
    
    return render(request, 'admin/customers/edit.html', {
        'form': form,
        'customer': customer,
        'customer_stats': customer_stats,
        'title': f'Edit Customer - {customer.full_name}'
    })

def get_customer_statistics(customer):
    """Get statistics for a customer"""
    try:
        from demos.models import DemoView, DemoRequest
        from enquiries.models import BusinessEnquiry
        
        demo_views = DemoView.objects.filter(user=customer).count()
        demo_requests = DemoRequest.objects.filter(user=customer).count()
        enquiries = BusinessEnquiry.objects.filter(user=customer).count()
        
        # Calculate engagement score (simple formula)
        engagement_score = min(100, (demo_views * 2 + demo_requests * 10 + enquiries * 15))
        
        # Get last activity
        last_activity = None
        last_demo_view = DemoView.objects.filter(user=customer).order_by('-viewed_at').first()
        if last_demo_view:
            last_activity = (last_demo_view.viewed_at, f"Viewed {last_demo_view.demo.title}")
        
        return {
            'total_demo_views': demo_views,
            'total_demo_requests': demo_requests,
            'total_enquiries': enquiries,
            'demo_views': demo_views,  # Template uses this
            'demo_requests': demo_requests,  # Template uses this
            'enquiries': enquiries,  # Template uses this
            'engagement_score': engagement_score,
            'account_age_days': (timezone.now() - customer.created_at).days if hasattr(customer, 'created_at') else 0,
            'last_activity': last_activity if last_activity else (None, 'No activity yet'),
        }
    except Exception as e:
        print(f"Error getting customer stats: {e}")
        return {
            'total_demo_views': 0,
            'total_demo_requests': 0,
            'total_enquiries': 0,
            'demo_views': 0,
            'demo_requests': 0,
            'enquiries': 0,
            'engagement_score': 0,
            'account_age_days': 0,
            'last_activity': (None, 'No activity'),
        }

@login_required
@user_passes_test(is_admin)
def admin_customer_detail(request, customer_id):
    """Admin view for customer details"""
    customer = get_object_or_404(User, id=customer_id, is_staff=False)
    customer_stats = get_customer_statistics(customer)
    
    return render(request, 'admin/customers/detail.html', {
        'customer': customer,
        'customer_stats': customer_stats,
        'title': f'Customer Details - {customer.full_name}'
    })

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_approve_customer(request, customer_id):
    """Approve customer account"""
    customer = get_object_or_404(User, id=customer_id, is_staff=False)
    
    if not customer.is_approved:
        customer.is_approved = True
        customer.is_active = True
        customer.save()
        
        # Send approval notification
        send_approval_notification(customer)
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True, 
                'message': f'{customer.full_name} has been approved and notified.'
            })
        else:
            messages.success(request, f'{customer.full_name} has been approved and notified.')
    
    return redirect('core:admin_users')

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_block_customer(request, customer_id):
    """Block customer account"""
    customer = get_object_or_404(User, id=customer_id, is_staff=False)
    
    if customer.is_active:
        customer.is_active = False
        customer.save()
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True, 
                'message': f'{customer.full_name} has been blocked.'
            })
        else:
            messages.warning(request, f'{customer.full_name} has been blocked.')
    
    return redirect('core:admin_users')

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_unblock_customer(request, customer_id):
    """Unblock customer account"""
    customer = get_object_or_404(User, id=customer_id, is_staff=False)
    
    if not customer.is_active:
        customer.is_active = True
        customer.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'{customer.full_name} has been unblocked.'
        })
    
    return JsonResponse({
        'success': False, 
        'message': 'Customer is already active.'
    })

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_delete_customer(request, customer_id):
    """Delete customer account"""
    customer = get_object_or_404(User, id=customer_id, is_staff=False)
    
    # Get statistics before deletion
    demo_views = customer.demo_views.count()
    demo_requests = customer.demo_requests.count()
    enquiries = customer.enquiries.count()
    
    customer_name = customer.full_name
    customer.delete()
    
    return JsonResponse({
        'success': True, 
        'message': f'{customer_name} has been permanently deleted.',
        'stats': {
            'demo_views': demo_views,
            'demo_requests': demo_requests,
            'enquiries': enquiries
        }
    })

@login_required
@user_passes_test(is_admin)
@require_http_methods(["POST"])
def admin_bulk_customer_actions(request):
    """Handle bulk actions on customers"""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        customer_ids = data.get('customer_ids', [])
        
        if not customer_ids:
            return JsonResponse({'success': False, 'message': 'No customers selected.'})
        
        customers = User.objects.filter(id__in=customer_ids, is_staff=False)
        count = customers.count()
        
        if count == 0:
            return JsonResponse({'success': False, 'message': 'No valid customers found.'})
        
        if action == 'approve':
            customers.update(is_approved=True, is_active=True)
            message = f'{count} customers approved successfully.'
            
        elif action == 'block':
            customers.update(is_active=False)
            message = f'{count} customers blocked successfully.'
            
        elif action == 'unblock':
            customers.update(is_active=True)
            message = f'{count} customers unblocked successfully.'
            
        elif action == 'delete':
            customers.delete()
            message = f'{count} customers deleted permanently.'
            
        else:
            return JsonResponse({'success': False, 'message': 'Invalid action.'})
        
        return JsonResponse({'success': True, 'message': message})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

@login_required
@user_passes_test(is_admin)
def admin_customer_export_view(request):
    """Export customer data to CSV"""
    # Get filtering parameters
    status_filter = request.GET.get('status')
    search = request.GET.get('search')
    
    # Filter customers (not admin/staff)
    customers = User.objects.filter(
        is_staff=False,
        is_superuser=False
    ).order_by('-created_at')
    
    # Apply filters
    if status_filter == 'pending':
        customers = customers.filter(is_approved=False)
    elif status_filter == 'approved':
        customers = customers.filter(is_approved=True)
    elif status_filter == 'blocked':
        customers = customers.filter(is_active=False)
    elif status_filter == 'active':
        customers = customers.filter(is_active=True, is_approved=True)
    
    if search:
        customers = customers.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(organization__icontains=search)
        )
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="customers_export_{timestamp}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Name', 'Email', 'Phone', 'Organization', 'Job Title',
        'Status', 'Email Verified', 'Registration Date', 'Last Login',
        'Referral Source', 'Country'
    ])
    
    # Write customer data
    for customer in customers:
        writer.writerow([
            customer.full_name,
            customer.email,
            customer.full_mobile,
            customer.organization or 'Not specified',
            customer.job_title or 'Not specified',
            'Active' if customer.is_approved and customer.is_active else 
            'Blocked' if customer.is_approved and not customer.is_active else 'Pending',
            'Yes' if customer.is_email_verified else 'No',
            customer.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            customer.last_login.strftime('%Y-%m-%d %H:%M:%S') if customer.last_login else 'Never',
            customer.get_referral_source_display() or 'Not specified',
            customer.get_country_code_display()
        ])
    
    return response

def send_approval_notification(customer):
    """Send account approval email to customer"""
    try:
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        # Check if HTML template exists, otherwise use plain text
        try:
            html_message = render_to_string('emails/account_approved.html', {
                'user': customer,
                'site_url': site_url
            })
        except:
            html_message = None
        
        # Plain text message
        plain_message = f"""
Dear {customer.first_name} {customer.last_name},

Great news! Your account has been approved.

You can now sign in to the Demo Portal and access all features.

Sign in here: {site_url}/auth/signin/

Your Account Details:
- Email: {customer.email}
- Organization: {customer.organization}
- Job Title: {customer.job_title}

If you have any questions, contact our support team.

Best regards,
Demo Portal Team
CHRP India
        """
        
        send_mail(
            subject='Account Approved - Demo Portal',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        return True
    except Exception as e:
        print(f"Error sending approval notification: {e}")
        return False

def send_customer_welcome_email(customer, created_by):
    """Send welcome email to admin-created customer"""
    try:
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        message = f"""
Dear {customer.first_name} {customer.last_name},

Welcome to Demo Portal!

Your account has been created by our admin team.

Account Details:
- Email: {customer.email}
- Organization: {customer.organization}
- Job Title: {customer.job_title}

Sign in here: {site_url}/auth/signin/

If you need to set/reset your password, use the "Forgot Password" option.

Best regards,
Demo Portal Team
CHRP India
        """
        
        send_mail(
            subject='Welcome to Demo Portal',
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            fail_silently=True,
        )
        
        return True
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False

def send_status_change_notification(customer, old_status, new_status):
    """Send notification when customer status changes"""
    old_approved, old_active = old_status
    new_approved, new_active = new_status
    
    # If approved status changed
    if old_approved != new_approved and new_approved:
        send_approval_notification(customer)
    
    # If blocked
    if old_active and not new_active:
        try:
            message = f"""
Dear {customer.first_name} {customer.last_name},

Your account has been temporarily suspended.

If you believe this is a mistake, please contact our support team.

Best regards,
Demo Portal Team
            """
            
            send_mail(
                subject='Account Status Update - Demo Portal',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[customer.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Error sending block notification: {e}"
                  )


def get_customer_statistics(customer):
    """Get statistics for a customer"""
    try:
        from demos.models import DemoView, DemoRequest
        from enquiries.models import BusinessEnquiry
        
        return {
            'total_demo_views': DemoView.objects.filter(user=customer).count(),
            'total_demo_requests': DemoRequest.objects.filter(user=customer).count(),
            'total_enquiries': BusinessEnquiry.objects.filter(user=customer).count(),
            'account_age_days': (timezone.now() - customer.created_at).days if hasattr(customer, 'created_at') else 0,
        }
    except Exception as e:
        print(f"Error getting customer stats: {e}")
        return {
            'total_demo_views': 0,
            'total_demo_requests': 0,
            'total_enquiries': 0,
            'account_age_days': 0,
        }


