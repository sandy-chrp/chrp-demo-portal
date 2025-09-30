# accounts/forms.py - Updated with Business Category Fields
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.conf import settings
from .models import CustomUser, BusinessCategory, BusinessSubCategory



class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    email = forms.EmailField(required=True)
    mobile = forms.CharField(max_length=10, required=True)
    country_code = forms.ChoiceField(choices=CustomUser.COUNTRY_CHOICES)
    job_title = forms.CharField(max_length=100, required=True)
    organization = forms.CharField(max_length=200, required=True)
    business_category = forms.ModelChoiceField(
        queryset=BusinessCategory.objects.filter(is_active=True),
        required=True
    )
    business_subcategory = forms.ModelChoiceField(
        queryset=BusinessSubCategory.objects.filter(is_active=True),
        required=False
    )
    referral_source = forms.ChoiceField(choices=CustomUser.REFERRAL_CHOICES, required=False)
    referral_message = forms.CharField(widget=forms.Textarea, required=False)
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'mobile', 'country_code',
                  'job_title', 'organization', 'business_category', 
                  'business_subcategory', 'referral_source', 'referral_message',
                  'password1', 'password2']

class OTPVerificationForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}'
        })
    )

# Keep all your existing forms unchanged
class SignInForm(forms.Form):
    """User login form"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'your@company.com',
            'required': True,
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your password',
            'required': True
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox'
        })
    )
    
    def clean_email(self):
        """Validate email format"""
        email = self.cleaned_data.get('email')
        if email:
            domain = email.split('@')[1].lower()
            blocked_domains = getattr(settings, 'BLOCKED_EMAIL_DOMAINS', [])
            
            if domain in blocked_domains:
                raise ValidationError('Please use your business email address.')
        
        return email

class ProfileForm(forms.ModelForm):
    """User profile edit form - UPDATED with category fields"""
    
    class Meta:
        model = CustomUser
        fields = [
            'first_name', 'last_name', 'mobile', 'country_code',
            'job_title', 'organization', 'business_category', 'business_subcategory'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'First Name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Last Name'
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '1234567890',
                'pattern': '[0-9]{10}'
            }),
            'country_code': forms.Select(attrs={
                'class': 'form-input'
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Your job title'
            }),
            'organization': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Company name'
            }),
            'business_category': forms.Select(attrs={
                'class': 'form-input',
                'id': 'profileCategorySelect'
            }),
            'business_subcategory': forms.Select(attrs={
                'class': 'form-input',
                'id': 'profileSubcategorySelect'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter active categories
        self.fields['business_category'].queryset = BusinessCategory.objects.filter(is_active=True)
        
        # If user has a category, populate subcategories
        if self.instance.pk and self.instance.business_category:
            self.fields['business_subcategory'].queryset = BusinessSubCategory.objects.filter(
                category=self.instance.business_category,
                is_active=True
            )
        else:
            self.fields['business_subcategory'].queryset = BusinessSubCategory.objects.none()
    
    def clean_mobile(self):
        """Validate mobile number"""
        mobile = self.cleaned_data.get('mobile')
        if mobile:
            if not mobile.isdigit() or len(mobile) != 10:
                raise ValidationError('Mobile number must be exactly 10 digits.')
            
            # Check if mobile already exists (excluding current user)
            country_code = self.cleaned_data.get('country_code', '+91')
            existing = CustomUser.objects.filter(
                mobile=mobile, 
                country_code=country_code
            ).exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError('An account with this mobile number already exists.')
        
        return mobile

class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with styling"""
    
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Current password',
            'autofocus': True
        })
    )
    
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'New password'
        })
    )
    
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm new password'
        })
    )

class ForgotPasswordForm(forms.Form):
    """Forgot password form"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your registered email',
            'required': True,
            'autofocus': True
        })
    )
    
    def clean_email(self):
        """Validate email exists"""
        email = self.cleaned_data.get('email')
        if email:
            try:
                user = CustomUser.objects.get(email=email)
                if not user.is_approved:
                    raise ValidationError(
                        'You are not a customer of the demo portal. Please sign up now.'
                    )
            except CustomUser.DoesNotExist:
                raise ValidationError(
                    'You are not a customer of the demo portal. Please sign up now.'
                )
        
        return email

class ResetPasswordForm(forms.Form):
    """Reset password form"""
    
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'New password',
            'required': True
        }),
        min_length=8,
        help_text='Password must be at least 8 characters long.'
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm new password',
            'required': True
        })
    )
    
    def clean(self):
        """Validate password confirmation"""
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2:
            if password1 != password2:
                raise ValidationError('Passwords do not match.')
        
        return cleaned_data