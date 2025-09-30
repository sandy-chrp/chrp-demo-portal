from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import update_session_auth_hash
from datetime import timedelta
import json
import secrets
import random

from demos.models import Demo, DemoView, DemoRequest
from enquiries.models import BusinessEnquiry
from .models import CustomUser, BusinessCategory, BusinessSubCategory
from .forms import (SignUpForm, ProfileForm, CustomPasswordChangeForm, 
                   ForgotPasswordForm, ResetPasswordForm, SignInForm)

# ===== HELPER FUNCTIONS =====

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def generate_otp():
    """Generate 6-digit OTP"""
    return str(random.randint(100000, 999999))

def send_otp_email(email, otp, name):
    """Send OTP verification email with detailed error handling"""
    from django.core.mail import EmailMessage
    from smtplib import SMTPException
    
    subject = "Email Verification - Demo Portal"
    message = f"""
Dear {name},

Your verification code for Demo Portal is:

{otp}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email.

Best regards,
Demo Portal Team
CHRP India
    """
    
    try:
        email_msg = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        email_msg.send(fail_silently=False)
        return {'success': True, 'error': None}
    
    except SMTPException as e:
        error_msg = str(e)
        print(f"SMTP Error: {error_msg}")
        
        # Check specific errors
        if "550" in error_msg or "recipient" in error_msg.lower():
            return {'success': False, 'error': 'invalid_recipient'}
        elif "authentication" in error_msg.lower():
            return {'success': False, 'error': 'auth_failed'}
        else:
            return {'success': False, 'error': 'smtp_error'}
    
    except Exception as e:
        print(f"General Email Error: {e}")
        return {'success': False, 'error': 'unknown'}
# ===== SIGNUP WITH OTP =====

def signup_view(request):
    """Step 1: Collect signup data and send OTP"""
    if request.user.is_authenticated:
        if hasattr(request.user, 'is_approved'):
            if request.user.is_approved:
                return redirect('customers:dashboard')
            else:
                return redirect('accounts:pending_approval')
        else:
            if request.user.is_staff or request.user.is_superuser:
                return redirect('core:admin_dashboard')
            else:
                return redirect('customers:dashboard')
    
    initial_data = {'country_code': '+91'}
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            
            # Check duplicate email
            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, 'An account with this email already exists.')
                return render(request, 'accounts/signup.html', {'form': form})
            
            # Store form data in session
            request.session['signup_data'] = {
                'first_name': form.cleaned_data['first_name'],
                'last_name': form.cleaned_data['last_name'],
                'email': email,
                'mobile': form.cleaned_data['mobile'],
                'country_code': form.cleaned_data['country_code'],
                'job_title': form.cleaned_data['job_title'],
                'organization': form.cleaned_data['organization'],
                'business_category_id': form.cleaned_data['business_category'].id if form.cleaned_data.get('business_category') else None,
                'business_subcategory_id': form.cleaned_data['business_subcategory'].id if form.cleaned_data.get('business_subcategory') else None,
                'referral_source': form.cleaned_data.get('referral_source', ''),
                'referral_message': form.cleaned_data.get('referral_message', ''),
                'password': form.cleaned_data['password1'],
            }
            
            # Generate and store OTP
            otp = generate_otp()
            request.session['signup_otp'] = otp
            request.session['otp_created_at'] = timezone.now().isoformat()
            
            full_name = f"{form.cleaned_data['first_name']} {form.cleaned_data['last_name']}"
            
            # Print OTP in console
            print("\n" + "="*60)
            print(f"OTP for {email}: {otp}")
            print("="*60 + "\n")
            
            # Send OTP email with error handling
            result = send_otp_email(email, otp, full_name)
            
            if result['success']:
                messages.success(request, f'Verification code sent to {email}. Please check your inbox.')
                return redirect('accounts:verify_otp')
            else:
                # Handle specific errors
                if result['error'] == 'invalid_recipient':
                    messages.error(
                        request, 
                        f'The email address "{email}" does not exist or cannot receive emails. Please check and try again.'
                    )
                elif result['error'] == 'auth_failed':
                    messages.error(
                        request,
                        'Email service authentication failed. Please contact support.'
                    )
                else:
                    messages.warning(
                        request,
                        f'Unable to send email to {email}. For testing, check the console for OTP or try another email address.'
                    )
                
                # Don't redirect - let user fix email
                return render(request, 'accounts/signup.html', {'form': form})
        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = SignUpForm(initial=initial_data)
    
    return render(request, 'accounts/signup.html', {'form': form})

def verify_otp_view(request):
    """Step 2: Verify OTP and create account"""
    signup_data = request.session.get('signup_data')
    if not signup_data:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('accounts:signup')
    
    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        stored_otp = request.session.get('signup_otp')
        otp_created_at = request.session.get('otp_created_at')
        
        if not stored_otp or not otp_created_at:
            messages.error(request, 'OTP expired. Please register again.')
            return redirect('accounts:signup')
        
        # Check OTP expiry (10 minutes)
        otp_time = timezone.datetime.fromisoformat(otp_created_at)
        if timezone.is_naive(otp_time):
            otp_time = timezone.make_aware(otp_time)
        
        if timezone.now() > otp_time + timedelta(minutes=10):
            messages.error(request, 'OTP expired. Please register again.')
            request.session.flush()
            return redirect('accounts:signup')
        
        # Verify OTP
        if entered_otp == stored_otp:
            try:
                # Create user account
                user = CustomUser(
                    username=signup_data['email'],
                    email=signup_data['email'],
                    first_name=signup_data['first_name'],
                    last_name=signup_data['last_name'],
                    mobile=signup_data['mobile'],
                    country_code=signup_data['country_code'],
                    job_title=signup_data['job_title'],
                    organization=signup_data['organization'],
                    referral_source=signup_data.get('referral_source', ''),
                    referral_message=signup_data.get('referral_message', ''),
                    is_email_verified=True,
                    is_approved=False,
                    is_active=True
                )
                user.set_password(signup_data['password'])
                
                # Set business category
                if signup_data.get('business_category_id'):
                    try:
                        user.business_category = BusinessCategory.objects.get(id=signup_data['business_category_id'])
                    except BusinessCategory.DoesNotExist:
                        pass
                
                # Set business subcategory
                if signup_data.get('business_subcategory_id'):
                    try:
                        user.business_subcategory = BusinessSubCategory.objects.get(id=signup_data['business_subcategory_id'])
                    except BusinessSubCategory.DoesNotExist:
                        pass
                
                user.save()
                
                # Clear session
                request.session.pop('signup_data', None)
                request.session.pop('signup_otp', None)
                request.session.pop('otp_created_at', None)
                
                messages.success(request, 'Account created successfully! Awaiting admin approval.')
                return redirect('accounts:pending_approval')
                
            except Exception as e:
                print(f"Account creation error: {e}")
                messages.error(request, f'Error creating account. Please try again.')
                return redirect('accounts:signup')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')
    
    # Calculate remaining time
    otp_created_at = request.session.get('otp_created_at')
    time_remaining = 0
    if otp_created_at:
        otp_time = timezone.datetime.fromisoformat(otp_created_at)
        if timezone.is_naive(otp_time):
            otp_time = timezone.make_aware(otp_time)
        expiry_time = otp_time + timedelta(minutes=10)
        time_remaining = max(0, int((expiry_time - timezone.now()).total_seconds()))
    
    context = {
        'email': signup_data.get('email', ''),
        'time_remaining': time_remaining
    }
    return render(request, 'accounts/verify_otp.html', context)

def resend_otp_view(request):
    """Resend OTP"""
    signup_data = request.session.get('signup_data')
    if not signup_data:
        messages.error(request, 'Session expired. Please register again.')
        return redirect('accounts:signup')
    
    # Generate new OTP
    otp = generate_otp()
    request.session['signup_otp'] = otp
    request.session['otp_created_at'] = timezone.now().isoformat()
    
    email = signup_data['email']
    full_name = f"{signup_data['first_name']} {signup_data['last_name']}"
    
    print("\n" + "="*60)
    print(f"Resend OTP for {email}: {otp}")
    print("="*60 + "\n")
    
    if send_otp_email(email, otp, full_name):
        messages.success(request, 'New verification code sent to your email.')
    else:
        messages.warning(request, 'Email service unavailable. Check console for OTP.')
    
    return redirect('accounts:verify_otp')

# ===== OTHER AUTHENTICATION VIEWS =====

def signin_view(request):
    """User login view"""
    if request.user.is_authenticated:
        if hasattr(request.user, 'is_approved'):
            if request.user.is_approved:
                return redirect('customers:dashboard')
            else:
                return redirect('accounts:pending_approval')
        else:
            if request.user.is_staff or request.user.is_superuser:
                return redirect('core:admin_dashboard')
            else:
                return redirect('customers:dashboard')
    
    if request.method == 'POST':
        form = SignInForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=email, password=password)
            if user:
                if hasattr(user, 'is_approved'):
                    if not user.is_approved:
                        messages.error(request, 'Your account is pending approval.')
                        return redirect('accounts:pending_approval')
                    
                    if not user.is_active:
                        messages.error(request, 'Your account has been blocked.')
                        return redirect('accounts:account_blocked')
                    
                    user.last_login_ip = get_client_ip(request)
                    user.save(update_fields=['last_login_ip'])
                    
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.full_name}!')
                    
                    next_url = request.GET.get('next')
                    if next_url and next_url.startswith('/dashboard/'):
                        return redirect(next_url)
                    else:
                        return redirect('customers:dashboard')
                else:
                    if not user.is_active:
                        messages.error(request, 'Your admin account has been disabled.')
                        return redirect('accounts:signin')
                    
                    if not (user.is_staff or user.is_superuser):
                        messages.error(request, 'You do not have admin access.')
                        return redirect('accounts:signin')
                    
                    login(request, user)
                    messages.success(request, 'Welcome back, Admin!')
                    
                    next_url = request.GET.get('next')
                    if next_url and next_url.startswith('/admin/'):
                        return redirect(next_url)
                    else:
                        return redirect('core:admin_dashboard')
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = SignInForm()
    
    return render(request, 'accounts/signin.html', {'form': form})

@login_required
def signout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('core:home')

def pending_approval_view(request):
    """Account pending approval page"""
    return render(request, 'accounts/pending_approval.html')

def account_blocked_view(request):
    """Account blocked page"""
    return render(request, 'accounts/account_blocked.html')

# ===== PROFILE VIEWS =====

@login_required
def profile(request):
    """User profile management"""
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if not request.user.check_password(current_password):
                messages.error(request, 'Current password is incorrect.')
                return HttpResponse(status=400)
            
            if new_password != confirm_password:
                messages.error(request, 'New passwords do not match.')
                return HttpResponse(status=400)
            
            if len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long.')
                return HttpResponse(status=400)
            
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            
            messages.success(request, 'Password changed successfully!')
            return HttpResponse(status=200)
        else:
            try:
                request.user.first_name = request.POST.get('first_name', '').strip()
                request.user.last_name = request.POST.get('last_name', '').strip()
                request.user.mobile = request.POST.get('mobile', '').strip()
                request.user.country_code = request.POST.get('country_code', '+91')
                request.user.job_title = request.POST.get('job_title', '').strip()
                request.user.organization = request.POST.get('organization', '').strip()
                
                if not request.user.first_name or not request.user.last_name:
                    messages.error(request, 'First name and last name are required.')
                    return HttpResponse(status=400)
                
                if not request.user.mobile or len(request.user.mobile) != 10:
                    messages.error(request, 'Please enter a valid 10-digit mobile number.')
                    return HttpResponse(status=400)
                
                request.user.save()
                messages.success(request, 'Profile updated successfully!')
                return HttpResponse(status=200)
                
            except Exception as e:
                messages.error(request, 'Error updating profile. Please try again.')
                return HttpResponse(status=500)
    
    try:
        total_demos_watched = DemoView.objects.filter(user=request.user).count()
        total_demo_requests = DemoRequest.objects.filter(user=request.user).count()
        total_enquiries = BusinessEnquiry.objects.filter(user=request.user).count()
        
        recent_demos = []
        recent_enquiries = []
        
        try:
            recent_demo_views = DemoView.objects.filter(
                user=request.user
            ).select_related('demo').order_by('-viewed_at')[:3]
            
            recent_demos = [view.demo for view in recent_demo_views]
        except:
            recent_demos = []
        
        try:
            recent_enquiries = BusinessEnquiry.objects.filter(
                user=request.user
            ).order_by('-created_at')[:3]
        except:
            recent_enquiries = []
        
        context = {
            'total_demos_watched': total_demos_watched,
            'total_demo_requests': total_demo_requests,
            'total_enquiries': total_enquiries,
            'recent_demos': recent_demos,
            'recent_enquiries': recent_enquiries,
        }
        
    except Exception as e:
        context = {
            'total_demos_watched': 0,
            'total_demo_requests': 0,
            'total_enquiries': 0,
            'recent_demos': [],
            'recent_enquiries': [],
        }
    
    return render(request, 'accounts/profile.html', context)

# ===== AJAX VIEWS =====

@csrf_exempt
@require_http_methods(["GET"])
def get_subcategories(request):
    """AJAX view to get subcategories"""
    category_id = request.GET.get('category_id')
    
    if not category_id:
        return JsonResponse({'subcategories': [], 'success': False})
    
    try:
        subcategories = BusinessSubCategory.objects.filter(
            category_id=category_id,
            is_active=True
        ).values('id', 'name').order_by('sort_order', 'name')
        
        return JsonResponse({
            'subcategories': list(subcategories),
            'success': True
        })
    except Exception as e:
        return JsonResponse({
            'subcategories': [],
            'success': False,
            'error': str(e)
        })
    
# Add these imports at the top if not already present
from django.utils.crypto import get_random_string

# Add these views to your accounts/views.py file

def forgot_password_view(request):
    """Forgot password view"""
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = CustomUser.objects.get(email=email)
                if (hasattr(user, 'is_approved') and user.is_approved) or user.is_staff or user.is_superuser:
                    # Generate reset token
                    token = secrets.token_urlsafe(32)
                    user.password_reset_token = token
                    user.password_reset_expires = timezone.now() + timedelta(hours=1)
                    user.save()
                    
                    # Send reset email
                    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
                    reset_url = f"{site_url}/auth/reset-password/{token}/"
                    subject = "Reset Your Password - Demo Portal"
                    message = f"""
Dear {user.full_name if hasattr(user, 'full_name') else user.username},

You requested a password reset. Click the link below to reset your password:

{reset_url}

This link will expire in 1 hour.

If you didn't request this, please ignore this email.

Best regards,
Demo Portal Team
                    """
                    
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                        fail_silently=False,
                    )
                    
                    messages.success(request, 'Password reset link sent to your email!')
                else:
                    messages.error(request, 'Account not authorized.')
            except CustomUser.DoesNotExist:
                messages.error(request, 'No account found with this email address.')
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'accounts/forgot_password.html', {'form': form})

def reset_password_view(request, token):
    """Reset password with token"""
    try:
        user = CustomUser.objects.get(
            password_reset_token=token,
            password_reset_expires__gt=timezone.now()
        )
    except CustomUser.DoesNotExist:
        messages.error(request, 'Invalid or expired reset link.')
        return redirect('accounts:forgot_password')
    
    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password1']
            user.set_password(password)
            user.password_reset_token = None
            user.password_reset_expires = None
            user.save()
            
            messages.success(request, 'Password reset successfully! Please sign in.')
            return redirect('accounts:signin')
    else:
        form = ResetPasswordForm()
    
    return render(request, 'accounts/reset_password.html', {'form': form, 'token': token})

def verify_email_view(request, token):
    """Email verification view"""
    try:
        user = CustomUser.objects.get(email_verification_token=token)
        user.is_email_verified = True
        user.email_verification_token = None
        user.save()
        
        messages.success(request, 'Email verified successfully!')
        return redirect('accounts:signin')
    except CustomUser.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('accounts:signin')

@login_required
def resend_verification_view(request):
    """Resend email verification"""
    if hasattr(request.user, 'is_email_verified'):
        if not request.user.is_email_verified:
            # Generate token and send email
            token = secrets.token_urlsafe(32)
            request.user.email_verification_token = token
            request.user.save()
            
            site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
            verification_url = f"{site_url}/auth/verify-email/{token}/"
            
            subject = "Verify Your Email - Demo Portal"
            message = f"""
Dear {request.user.full_name},

Please verify your email address by clicking the link below:

{verification_url}

Best regards,
Demo Portal Team
            """
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [request.user.email])
            messages.success(request, 'Verification email sent!')
        else:
            messages.info(request, 'Email already verified.')
    else:
        messages.info(request, 'Email verification not applicable.')
    
    return redirect('accounts:profile')

@login_required
def edit_profile_view(request):
    """Edit user profile"""
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)
    
    return render(request, 'accounts/edit_profile.html', {'form': form})

@login_required
def change_password_view(request):
    """Change user password"""
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Password changed successfully!')
            return redirect('accounts:profile')
    else:
        form = CustomPasswordChangeForm(request.user)
    
    return render(request, 'accounts/change_password.html', {'form': form})

@csrf_exempt
@require_http_methods(["POST"])
def check_email_exists(request):
    """AJAX view to check if email exists"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        exists = CustomUser.objects.filter(email=email).exists()
        return JsonResponse({'exists': exists})
    except:
        return JsonResponse({'exists': False})

@csrf_exempt
@require_http_methods(["POST"])
def contact_sales_view(request):
    """Handle contact sales form submission"""
    try:
        data = json.loads(request.body)
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you! Our sales team will contact you soon.'
        })
    except:
        return JsonResponse({
            'success': False,
            'message': 'Something went wrong. Please try again.'
        })

@csrf_exempt
@require_http_methods(["GET"])
def get_country_from_ip(request):
    """AJAX view to get country based on IP"""
    client_ip = get_client_ip(request)
    
    try:
        if client_ip and client_ip.startswith(('49.', '117.', '122.', '103.', '115.')):
            return JsonResponse({
                'country_code': '+91',
                'country_name': 'India',
                'detected': True
            })
        else:
            return JsonResponse({
                'country_code': '+1',
                'country_name': 'United States',
                'detected': False
            })
    except:
        return JsonResponse({
            'country_code': '+91',
            'country_name': 'India',
            'detected': False
        })    