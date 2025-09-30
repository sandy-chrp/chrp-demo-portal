# enquiries/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
import uuid

User = get_user_model()

class EnquiryCategory(models.Model):
    """Categories for organizing enquiries"""
    
    name = models.CharField(max_length=100, unique=True, verbose_name="Category Name")
    description = models.TextField(blank=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Sort Order")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'enquiry_categories'
        verbose_name = 'Enquiry Category'
        verbose_name_plural = 'Enquiry Categories'
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name

class BusinessEnquiry(models.Model):
    """Business enquiries from customers"""
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('answered', 'Answered'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Enquiry Information
    enquiry_id = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True,
        verbose_name="Enquiry ID"
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='enquiries',
        verbose_name="Customer"
    )
    category = models.ForeignKey(
        EnquiryCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enquiries',
        verbose_name="Category"
    )
    
    # Contact Information
    first_name = models.CharField(max_length=50, verbose_name="First Name")
    last_name = models.CharField(max_length=50, verbose_name="Last Name")
    business_email = models.EmailField(verbose_name="Business Email")
    
    phone_validator = RegexValidator(
        regex=r'^\d{10}$',
        message="Phone number must be exactly 10 digits."
    )
    mobile = models.CharField(
        validators=[phone_validator], 
        max_length=10,
        verbose_name="Mobile Number"
    )
    country_code = models.CharField(max_length=5, default='+91', verbose_name="Country Code")
    
    # Business Details
    job_title = models.CharField(max_length=100, verbose_name="Job Title")
    organization = models.CharField(max_length=200, verbose_name="Organization Name")
    
    # Enquiry Content
    subject = models.CharField(
        max_length=200, 
        blank=True,
        verbose_name="Subject"
    )
    message = models.TextField(verbose_name="Message/Query")
    
    # Status & Priority
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='open',
        verbose_name="Status"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium',
        verbose_name="Priority"
    )
    
    # Admin Management
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_enquiries',
        verbose_name="Assigned To"
    )
    admin_notes = models.TextField(blank=True, verbose_name="Admin Notes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Closed At")
    
    # Response Time Tracking
    first_response_at = models.DateTimeField(null=True, blank=True)
    last_response_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'business_enquiries'
        verbose_name = 'Business Enquiry'
        verbose_name_plural = 'Business Enquiries'
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.enquiry_id:
            # Generate unique enquiry ID: ENQ-YYYY-XXXXXX
            from datetime import datetime
            year = datetime.now().year
            count = BusinessEnquiry.objects.filter(
                created_at__year=year
            ).count() + 1
            self.enquiry_id = f"ENQ-{year}-{count:06d}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.enquiry_id} - {self.first_name} {self.last_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def full_mobile(self):
        return f"{self.country_code}{self.mobile}"
    
    @property
    def is_overdue(self):
        """Check if enquiry is overdue (no response in 24 hours)"""
        from django.utils import timezone
        from datetime import timedelta
        
        if self.status in ['answered', 'closed']:
            return False
        
        cutoff_time = timezone.now() - timedelta(hours=24)
        return self.created_at < cutoff_time and not self.first_response_at

class EnquiryResponse(models.Model):
    """Responses to enquiries (admin replies)"""
    
    enquiry = models.ForeignKey(
        BusinessEnquiry,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name="Enquiry"
    )
    
    # Response Content
    response_text = models.TextField(verbose_name="Response Message")
    is_internal_note = models.BooleanField(
        default=False,
        verbose_name="Internal Note",
        help_text="Internal notes are not visible to customers"
    )
    
    # Response Details
    responded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='enquiry_responses',
        verbose_name="Responded By"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Responded At")
    
    # Email Status
    email_sent = models.BooleanField(default=False, verbose_name="Email Sent")
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'enquiry_responses'
        verbose_name = 'Enquiry Response'
        verbose_name_plural = 'Enquiry Responses'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Response to {self.enquiry.enquiry_id} by {self.responded_by.username}"