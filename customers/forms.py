from django import forms
from django.contrib.auth import get_user_model
from demos.models import Demo, DemoRequest, TimeSlot
from enquiries.models import BusinessEnquiry, EnquiryCategory

User = get_user_model()

class DemoRequestForm(forms.ModelForm):
    """Form for requesting live demo sessions"""
    
    demo = forms.ModelChoiceField(
        queryset=Demo.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        empty_label="Select a demo"
    )
    
    requested_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'min': timezone.now().date().strftime('%Y-%m-%d'),
            'required': True
        })
    )
    
    requested_time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select',
            'required': True
        }),
        empty_label="Select time slot"
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Any specific requirements or notes for the demo session...'
        }),
        required=False
    )
    
    class Meta:
        model = DemoRequest
        fields = ['demo', 'requested_date', 'requested_time_slot', 'notes']
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Filter demos based on user access
            accessible_demos = Demo.objects.filter(is_active=True).filter(
                models.Q(target_customers=user) | models.Q(target_customers__isnull=True)
            )
            self.fields['demo'].queryset = accessible_demos
    
    def clean_requested_date(self):
        date = self.cleaned_data['requested_date']
        
        # Check if date is not in the past
        if date < timezone.now().date():
            raise forms.ValidationError("Cannot request demo for past dates.")
        
        # Check if date is not Sunday
        if date.weekday() == 6:
            raise forms.ValidationError("Demo requests cannot be made for Sundays.")
        
        return date

class BusinessEnquiryForm(forms.ModelForm):
    """Form for sending business enquiries"""
    
    category = forms.ModelChoiceField(
        queryset=EnquiryCategory.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        required=False,
        empty_label="Select category (optional)"
    )
    
    subject = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Brief subject of your enquiry'
        }),
        max_length=200,
        required=False
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Please describe your business requirements, questions, or any specific information you need...',
            'required': True
        })
    )
    
    class Meta:
        model = BusinessEnquiry
        fields = ['category', 'subject', 'message']
    
    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        
        if len(message) < 10:
            raise forms.ValidationError("Message must be at least 10 characters long.")
        
        return message

class ContactSalesForm(forms.Form):
    """Form for contacting sales team"""
    
    subject = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Subject of your message'
        }),
        max_length=200
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'Tell us about your business needs, budget, timeline, or any specific requirements...'
        })
    )
    
    priority = forms.ChoiceField(
        choices=[
            ('normal', 'Normal'),
            ('high', 'High Priority'),
            ('urgent', 'Urgent'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        initial='normal'
    )
    
    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        
        if len(message) < 20:
            raise forms.ValidationError("Please provide more details (minimum 20 characters).")
        
        return message

class DemoFeedbackForm(forms.Form):
    """Form for demo feedback"""
    
    rating = forms.ChoiceField(
        choices=[(i, f"{i} Star{'s' if i > 1 else ''}") for i in range(1, 6)],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        }),
        required=False
    )
    
    feedback_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Share your thoughts about this demo...'
        })
    )
    
    def clean_feedback_text(self):
        feedback = self.cleaned_data['feedback_text'].strip()
        
        if len(feedback) < 5:
            raise forms.ValidationError("Feedback must be at least 5 characters long.")
        
        return feedback

# Security Forms
class SecurityViolationForm(forms.ModelForm):
    """Form for reporting security violations"""
    
    class Meta:
        model = SecurityViolation
        fields = ['violation_type', 'description', 'page_url']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs.update({
            'class': 'form-control',
            'rows': 3
        })
        self.fields['page_url'].widget.attrs.update({
            'class': 'form-control'
        })