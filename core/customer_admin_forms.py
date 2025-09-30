# core/customer_admin_forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
import re

User = get_user_model()

# Add these imports at top
from accounts.models import BusinessCategory, BusinessSubCategory

# Update CustomerCreateForm class
class CustomerCreateForm(forms.ModelForm):
    """Form for admin to create new customers"""
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control'
        }),
        help_text='Password must be at least 8 characters long.'
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control'
        }),
        help_text='Enter the same password as above.'
    )
    
    # ADD THESE FIELDS
    business_category = forms.ModelChoiceField(
        queryset=BusinessCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'adminCategorySelect'
        }),
        help_text='Select customer business category (optional).'
    )
    
    business_subcategory = forms.ModelChoiceField(
        queryset=BusinessSubCategory.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'adminSubcategorySelect',
            'disabled': 'disabled'
        }),
        help_text='Select subcategory after choosing category (optional).'
    )
    
    skip_email_validation = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Skip business email domain validation (use with caution).'
    )
    verify_email_otp = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Send OTP to verify email address.'
    )
    send_welcome_email = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Send welcome email to customer.'
    )
    
    is_approved = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Approve account immediately.'
    )
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'mobile', 'country_code',
            'job_title', 'organization', 'business_category', 'business_subcategory',
            'referral_source', 'referral_message'
        ]
        
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'required': True
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'required': True
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'required': True
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': '[0-9]{10}',
                'maxlength': '10',
                'required': True
            }),
            'country_code': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'organization': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'referral_source': forms.Select(attrs={
                'class': 'form-select'
            }),
            'referral_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Mark required fields
        required_fields = ['first_name', 'last_name', 'email', 'mobile', 'country_code']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # Populate subcategories if category is selected
        if 'business_category' in self.data:
            try:
                category_id = int(self.data.get('business_category'))
                self.fields['business_subcategory'].queryset = BusinessSubCategory.objects.filter(
                    category_id=category_id,
                    is_active=True
                ).order_by('sort_order', 'name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.business_category:
            self.fields['business_subcategory'].queryset = BusinessSubCategory.objects.filter(
                category=self.instance.business_category,
                is_active=True
            ).order_by('sort_order', 'name')
    
    def clean_email(self):
        """Validate business email with skip option"""
        email = self.cleaned_data.get('email', '').lower().strip()
        skip_validation = self.cleaned_data.get('skip_email_validation', False)
        
        if not email:
            raise ValidationError('Email is required.')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise ValidationError('A customer with this email already exists.')
        
        # Skip domain validation if admin chose to
        if skip_validation:
            return email
        
        # Validate business email domain
        from django.conf import settings
        blocked_domains = getattr(settings, 'BLOCKED_EMAIL_DOMAINS', [
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'ymail.com', 'aol.com', 'icloud.com', 'live.com'
        ])
        
        domain = email.split('@')[1].lower()
        if domain in blocked_domains:
            raise ValidationError(
                f'Personal email domain ({domain}) not allowed. Check "Skip validation" to override.'
            )
        
        return email
    
    def clean_mobile(self):
        """Validate mobile number"""
        mobile = self.cleaned_data.get('mobile', '').strip()
        
        if not mobile:
            raise ValidationError('Mobile number is required.')
        
        mobile = re.sub(r'\D', '', mobile)
        
        if len(mobile) != 10:
            raise ValidationError('Mobile number must be exactly 10 digits.')
        
        return mobile
    
    def clean_password(self):
        """Validate password"""
        password = self.cleaned_data.get('password')
        
        if not password:
            raise ValidationError('Password is required.')
        
        try:
            validate_password(password)
        except ValidationError as e:
            raise ValidationError(e.messages)
        
        return password
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise ValidationError({
                    'confirm_password': 'Passwords do not match.'
                })
        
        # Generate username from email
        email = cleaned_data.get('email')
        if email:
            username = email.split('@')[0]
            counter = 1
            original_username = username
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1
            cleaned_data['username'] = username
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save customer with all fields"""
        user = super().save(commit=False)
        
        user.username = self.cleaned_data['username']
        user.set_password(self.cleaned_data['password'])
        user.is_email_verified = True
        user.is_staff = False
        user.is_superuser = False
        
        if commit:
            user.save()
        
        return user

class CustomerEditForm(forms.ModelForm):
    """Form for admin to edit existing customers"""
    
    change_password = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Check this box to change the customer\'s password.'
    )
    
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control'
        }),
        help_text='Leave blank to keep current password.'
    )
    
    confirm_new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control'
        }),
        help_text='Enter the same password as above, for verification.'
    )
    
    # ADD THESE FIELDS
    business_category = forms.ModelChoiceField(
        queryset=BusinessCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'editCategorySelect'
        }),
        help_text='Select customer business category (optional).'
    )
    
    business_subcategory = forms.ModelChoiceField(
        queryset=BusinessSubCategory.objects.none(),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'editSubcategorySelect'
        }),
        help_text='Select subcategory after choosing category (optional).'
    )
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'mobile', 'country_code',
            'job_title', 'organization', 'business_category', 'business_subcategory',
            'referral_source', 'referral_message',
            'is_approved', 'is_active', 'is_email_verified'
        ]
        
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control'
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'pattern': '[0-9]{10}',
                'maxlength': '10'
            }),
            'country_code': forms.Select(attrs={
                'class': 'form-select'
            }),
            'job_title': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'organization': forms.TextInput(attrs={
                'class': 'form-control'
            }),
            'referral_source': forms.Select(attrs={
                'class': 'form-select'
            }),
            'referral_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'is_approved': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_email_verified': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Mark required fields
        required_fields = ['first_name', 'last_name', 'email', 'mobile']
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # Populate subcategories if category is selected
        if 'business_category' in self.data:
            try:
                category_id = int(self.data.get('business_category'))
                self.fields['business_subcategory'].queryset = BusinessSubCategory.objects.filter(
                    category_id=category_id,
                    is_active=True
                ).order_by('sort_order', 'name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk and self.instance.business_category:
            self.fields['business_subcategory'].queryset = BusinessSubCategory.objects.filter(
                category=self.instance.business_category,
                is_active=True
            ).order_by('sort_order', 'name')
    
    def clean_email(self):
        """Validate email on edit"""
        email = self.cleaned_data.get('email', '').lower().strip()
        
        if not email:
            raise ValidationError('Email is required.')
        
        # Check if email exists for other users
        existing_user = User.objects.filter(email=email).exclude(pk=self.instance.pk).first()
        if existing_user:
            raise ValidationError('A customer with this email already exists.')
        
        # Validate business email domain
        from django.conf import settings
        blocked_domains = getattr(settings, 'BLOCKED_EMAIL_DOMAINS', [
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'ymail.com', 'aol.com', 'icloud.com', 'live.com'
        ])
        
        domain = email.split('@')[1].lower()
        if domain in blocked_domains:
            raise ValidationError(
                f'Business email required. Personal email domains ({domain}) are not allowed.'
            )
        
        return email
    
    def clean_mobile(self):
        """Validate mobile number"""
        mobile = self.cleaned_data.get('mobile', '').strip()
        
        if not mobile:
            raise ValidationError('Mobile number is required.')
        
        mobile = re.sub(r'\D', '', mobile)
        
        if len(mobile) != 10:
            raise ValidationError('Mobile number must be exactly 10 digits.')
        
        return mobile
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        change_password = cleaned_data.get('change_password')
        new_password = cleaned_data.get('new_password')
        confirm_new_password = cleaned_data.get('confirm_new_password')
        
        if change_password:
            if not new_password:
                raise ValidationError({
                    'new_password': 'New password is required when changing password.'
                })
            
            try:
                validate_password(new_password)
            except ValidationError as e:
                raise ValidationError({
                    'new_password': e.messages
                })
            
            if new_password != confirm_new_password:
                raise ValidationError({
                    'confirm_new_password': 'Passwords do not match.'
                })
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save customer with optional password change"""
        user = super().save(commit=False)
        
        if self.cleaned_data.get('change_password') and self.cleaned_data.get('new_password'):
            user.set_password(self.cleaned_data['new_password'])
        
        if commit:
            user.save()
        
        return user

class CustomerSearchForm(forms.Form):
    """Form for searching customers"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'off'
        })
    )
    
    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'All Customers'),
            ('active', 'Active'),
            ('pending', 'Pending Approval'),
            ('blocked', 'Blocked'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )