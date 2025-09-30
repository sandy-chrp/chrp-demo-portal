
# demos/forms.py - Complete with all imports and forms

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from .models import DemoRequest, DemoFeedback, Demo, TimeSlot
from accounts.models import BusinessCategory, BusinessSubCategory
from accounts.models import CustomUser, BusinessCategory, BusinessSubCategory  # Add this line

# Get the user model (CustomUser)
User = get_user_model()


class DemoRequestForm(forms.ModelForm):
    """Form for requesting demo sessions"""
    
    class Meta:
        model = DemoRequest
        fields = [
            'requested_date', 
            'requested_time_slot', 
            'notes',
            'postal_code',
            'city',
            'country_region',
            'timezone'
        ]
        widgets = {
            'requested_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'required': True
            }),
            'requested_time_slot': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any specific topics or questions you\'d like covered?'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter postal/ZIP code'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter city'
            }),
            'country_region': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country/Region code'
            }),
            'timezone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., GMT+5:30'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active time slots
        self.fields['requested_time_slot'].queryset = TimeSlot.objects.filter(is_active=True)
    
    def clean_requested_date(self):
        from django.utils import timezone
        from datetime import timedelta
        
        requested_date = self.cleaned_data['requested_date']
        
        # Check if date is not in the past
        if requested_date < timezone.now().date():
            raise ValidationError("Cannot request demos for past dates.")
        
        # Check if date is not Sunday
        if requested_date.weekday() == 6:
            raise ValidationError("Demo sessions are not available on Sundays.")
        
        # Check if date is within allowed advance booking period (30 days)
        max_advance_date = timezone.now().date() + timedelta(days=30)
        if requested_date > max_advance_date:
            raise ValidationError("Demo sessions can only be booked up to 30 days in advance.")
        
        return requested_date


class DemoFeedbackForm(forms.ModelForm):
    """Form for submitting demo feedback"""
    
    class Meta:
        model = DemoFeedback
        fields = ['rating', 'feedback_text']
        widgets = {
            'rating': forms.RadioSelect(
                choices=[(i, i) for i in range(1, 6)],
                attrs={'class': 'form-check-input'}
            ),
            'feedback_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Share your thoughts about this demo...',
                'required': True
            })
        }
    
    def clean_feedback_text(self):
        feedback_text = self.cleaned_data.get('feedback_text')
        if feedback_text and len(feedback_text.strip()) < 10:
            raise ValidationError("Feedback must be at least 10 characters long.")
        return feedback_text.strip()


class DemoFilterForm(forms.Form):
    """Form for filtering demos"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search demos...'
        })
    )
    
    demo_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + Demo.DEMO_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    category = forms.ModelChoiceField(
        required=False,
        queryset=BusinessCategory.objects.filter(is_active=True),
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('popular', 'Most Popular'),
            ('featured', 'Featured First')
        ],
        initial='newest',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class AdminDemoForm(forms.ModelForm):
    """Admin form for creating/editing demos with business category targeting"""
    
    # Business Categories - ManyToMany field
    target_business_categories = forms.ModelMultipleChoiceField(
        queryset=BusinessCategory.objects.filter(is_active=True).order_by('sort_order', 'name'),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input category-checkbox'
        }),
        help_text='Select business categories this demo is relevant for. Leave empty for all categories.'
    )
    
    # Business Subcategories - ManyToMany field
    target_business_subcategories = forms.ModelMultipleChoiceField(
        queryset=BusinessSubCategory.objects.filter(is_active=True).order_by('sort_order', 'name'),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input subcategory-checkbox'
        }),
        help_text='Select specific subcategories this demo is relevant for. Leave empty for all subcategories.'
    )
    
    # Customer Selection - ManyToMany field
    target_customers = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.filter(
            is_approved=True,
            is_active=True
        ).order_by('first_name', 'last_name'),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input customer-checkbox'
        }),
        help_text="Select specific customers who can access this demo. Leave empty for all customers."
    )
    
    # Helper field for "All Customers" option
    all_customers = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'allCustomersCheckbox'
        }),
        label="Available to All Customers"
    )
    
    # Helper field for "All Business Categories" option
    all_business_categories = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'allBusinessCategoriesCheckbox'
        }),
        label="Available to All Business Categories"
    )
    
    class Meta:
        model = Demo
        fields = [
            'title', 
            'description', 
            'demo_type',
            'video_file', 
            'thumbnail', 
            'duration', 
            'target_business_categories',
            'target_business_subcategories',
            'target_customers',
            'is_featured',
            'is_active',
            'sort_order'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter demo title',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe what this demo showcases...',
                'required': True
            }),
            'demo_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'video_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'video/mp4,video/avi,video/mov,video/wmv'
            }),
            'thumbnail': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/jpeg,image/jpg,image/png,image/webp'
            }),
            'duration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'HH:MM:SS'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'value': 0
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set initial values for helper fields based on existing data
        if self.instance.pk:
            # Existing demo - check if categories/customers are selected
            if not self.instance.target_business_categories.exists():
                self.fields['all_business_categories'].initial = True
            else:
                self.fields['all_business_categories'].initial = False
                
            if not self.instance.target_customers.exists():
                self.fields['all_customers'].initial = True
            else:
                self.fields['all_customers'].initial = False
        
        # Improve field labels
        self.fields['demo_type'].label = "Demo Type"
        self.fields['is_featured'].label = "Feature this demo"
        self.fields['is_active'].label = "Make demo active"
        self.fields['sort_order'].label = "Display Order"
    
    def clean_title(self):
        """Validate title"""
        title = self.cleaned_data.get('title')
        if not title or not title.strip():
            raise ValidationError("Title cannot be empty.")
        return title.strip()
    
    def clean_duration(self):
        """Validate and convert duration string to timedelta"""
        duration_str = self.cleaned_data.get('duration')
        
        if not duration_str:
            return None
            
        # Remove any extra spaces
        duration_str = str(duration_str).strip()
        
        # If it's already a timedelta, return it
        if isinstance(duration_str, timedelta):
            return duration_str
            
        # Parse HH:MM:SS or MM:SS format
        try:
            parts = duration_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return timedelta(hours=hours, minutes=minutes, seconds=seconds)
            elif len(parts) == 2:
                minutes, seconds = map(int, parts)
                return timedelta(minutes=minutes, seconds=seconds)
            else:
                raise ValueError("Invalid format")
        except (ValueError, AttributeError):
            raise ValidationError("Duration must be in HH:MM:SS or MM:SS format")
    
    def clean_video_file(self):
        """Validate video file"""
        video = self.cleaned_data.get('video_file')
        if video:
            # Check file size (max 100MB)
            if video.size > 100 * 1024 * 1024:
                raise ValidationError("Video file size cannot exceed 100MB.")
            
            # Check file extension
            ext = video.name.split('.')[-1].lower()
            if ext not in ['mp4', 'avi', 'mov', 'wmv']:
                raise ValidationError("Invalid video format. Allowed: MP4, AVI, MOV, WMV")
        
        return video
    
    def clean_thumbnail(self):
        """Validate thumbnail image"""
        thumbnail = self.cleaned_data.get('thumbnail')
        if thumbnail:
            # Check file size (max 5MB)
            if thumbnail.size > 5 * 1024 * 1024:
                raise ValidationError("Thumbnail size cannot exceed 5MB.")
            
            # Check file extension
            ext = thumbnail.name.split('.')[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                raise ValidationError("Invalid image format. Allowed: JPG, PNG, WebP")
        
        return thumbnail
    
    def clean_target_business_subcategories(self):
        """Validate that selected subcategories belong to selected categories"""
        categories = self.cleaned_data.get('target_business_categories', [])
        subcategories = self.cleaned_data.get('target_business_subcategories', [])
        
        if subcategories and not categories:
            # If subcategories selected but no categories, it's okay
            # The subcategories themselves define the targeting
            return subcategories
            
        if subcategories and categories:
            # Validate that subcategories belong to selected categories
            valid_subcategories = BusinessSubCategory.objects.filter(
                category__in=categories
            )
            
            invalid_subcategories = []
            for subcat in subcategories:
                if subcat not in valid_subcategories:
                    invalid_subcategories.append(str(subcat))
            
            if invalid_subcategories:
                raise ValidationError(
                    f"The following subcategories don't belong to selected categories: {', '.join(invalid_subcategories)}"
                )
        
        return subcategories
    
    def clean(self):
        """Overall form validation"""
        cleaned_data = super().clean()
        
        # Handle "all customers" logic
        all_customers = cleaned_data.get('all_customers')
        target_customers = cleaned_data.get('target_customers')
        
        if all_customers:
            # Clear target customers if "all" is selected
            cleaned_data['target_customers'] = []
        elif not target_customers:
            # If not "all" and no specific customers, that's fine
            # It means available to all customers
            pass
        
        # Handle "all business categories" logic
        all_categories = cleaned_data.get('all_business_categories')
        target_categories = cleaned_data.get('target_business_categories')
        
        if all_categories:
            # Clear target categories if "all" is selected
            cleaned_data['target_business_categories'] = []
            cleaned_data['target_business_subcategories'] = []
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the demo with ManyToMany relationships"""
        demo = super().save(commit=False)
        
        # Ensure slug is handled by the model
        if not demo.slug:
            demo.slug = None  # Model's save() will generate it
        
        if commit:
            demo.save()
            
            # Save ManyToMany relationships
            # Business Categories
            if self.cleaned_data.get('all_business_categories'):
                demo.target_business_categories.clear()
                demo.target_business_subcategories.clear()
            else:
                categories = self.cleaned_data.get('target_business_categories', [])
                demo.target_business_categories.set(categories)
                
                subcategories = self.cleaned_data.get('target_business_subcategories', [])
                demo.target_business_subcategories.set(subcategories)
            
            # Customers
            if self.cleaned_data.get('all_customers'):
                demo.target_customers.clear()
            else:
                customers = self.cleaned_data.get('target_customers', [])
                demo.target_customers.set(customers)
            
            # Save the form's many-to-many data
            self.save_m2m()
        
        return demo