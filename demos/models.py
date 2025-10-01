# demos/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import uuid
import os

User = get_user_model()

def demo_video_path(instance, filename):
    """Generate path for demo video uploads"""
    ext = filename.split('.')[-1]
    filename = f"{instance.slug}_{uuid.uuid4().hex[:8]}.{ext}"
    return f'demos/videos/{filename}'

def demo_thumbnail_path(instance, filename):
    """Generate path for demo thumbnail uploads"""
    ext = filename.split('.')[-1]
    filename = f"thumb_{instance.slug}_{uuid.uuid4().hex[:8]}.{ext}"
    return f'demos/thumbnails/{filename}'

class DemoCategory(models.Model):
    """Categories for organizing demos"""
    
    name = models.CharField(max_length=100, unique=True, verbose_name="Category Name")
    description = models.TextField(blank=True, verbose_name="Description")
    icon = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Emoji or CSS icon class",
        verbose_name="Icon"
    )
    slug = models.SlugField(unique=True, blank=True)
    is_active = models.BooleanField(default=True, verbose_name="Active")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Sort Order")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'demo_categories'
        verbose_name = 'Demo Category'
        verbose_name_plural = 'Demo Categories'
        ordering = ['sort_order', 'name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name

# demos/models.py - Updated Demo model without DemoCategory

class Demo(models.Model):
    """Demo videos/presentations"""
    
    # Basic Information
    title = models.CharField(max_length=200, verbose_name="Demo Title")
    description = models.TextField(verbose_name="Description")
    slug = models.SlugField(unique=True, blank=True, max_length=250)
    
    # REMOVED: category ForeignKey field
    
    # Business Category Targeting (MAIN CATEGORIZATION)
    target_business_categories = models.ManyToManyField(
        'accounts.BusinessCategory',
        blank=True,
        related_name='available_demos',
        verbose_name="Target Business Categories",
        help_text="Select business categories this demo is relevant for. Leave empty for all categories."
    )
    
    target_business_subcategories = models.ManyToManyField(
        'accounts.BusinessSubCategory',
        blank=True,
        related_name='available_demos',
        verbose_name="Target Business Subcategories",
        help_text="Select specific subcategories this demo is relevant for. Leave empty for all subcategories."
    )
    
    # Demo Type (Optional - for internal organization)
    DEMO_TYPE_CHOICES = [
        ('product', 'Product Demo'),
        ('feature', 'Feature Demo'),
        ('overview', 'Overview Demo'),
        ('tutorial', 'Tutorial'),
        ('case_study', 'Case Study'),
        ('webinar', 'Webinar Recording'),
    ]
    demo_type = models.CharField(
        max_length=20,
        choices=DEMO_TYPE_CHOICES,
        default='product',
        verbose_name="Demo Type"
    )
    
    # Media Files
    video_file = models.FileField(
        upload_to=demo_video_path,
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'avi', 'mov', 'wmv'])],
        verbose_name="Video File"
    )
    thumbnail = models.ImageField(
        upload_to=demo_thumbnail_path,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
        verbose_name="Thumbnail Image"
    )
    
    # Video Properties
    duration = models.DurationField(
        null=True, 
        blank=True, 
        help_text="Duration in HH:MM:SS format",
        verbose_name="Duration"
    )
    
    # Customer Access Control
    target_customers = models.ManyToManyField(
        'accounts.CustomUser',
        blank=True,
        related_name='accessible_demos',
        verbose_name="Target Customers",
        help_text="Select specific customers who can access this demo. Leave empty for all customers."
    )
    
    # Engagement Stats
    views_count = models.PositiveIntegerField(default=0, verbose_name="Views Count")
    likes_count = models.PositiveIntegerField(default=0, verbose_name="Likes Count")
    
    # Status & Visibility
    is_active = models.BooleanField(default=True, verbose_name="Active")
    is_featured = models.BooleanField(default=False, verbose_name="Featured")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Sort Order")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    
    # Creator (Admin who uploaded)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_demos',
        verbose_name="Created By"
    )
    
    class Meta:
        db_table = 'demos'
        verbose_name = 'Demo'
        verbose_name_plural = 'Demos'
        ordering = ['-is_featured', 'sort_order', '-created_at']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            if not base_slug:
                base_slug = 'demo'
            
            unique_slug = base_slug
            counter = 1
            while Demo.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = unique_slug
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title
    
    @property
    def formatted_duration(self):
        if self.duration:
            total_seconds = int(self.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours:
                return f"{hours}:{minutes:02d}:{seconds:02d}"
            return f"{minutes}:{seconds:02d}"
        return "00:00"
    
    # Business Category Access Methods
    @property
    def is_for_all_business_categories(self):
        """Check if demo is available for all business categories"""
        return self.target_business_categories.count() == 0
    
    @property
    def is_for_all_business_subcategories(self):
        """Check if demo is available for all business subcategories"""
        return self.target_business_subcategories.count() == 0
    
    def is_available_for_business_category(self, category):
        """Check if demo is available for a specific business category"""
        if self.is_for_all_business_categories:
            return True
        if category:
            return self.target_business_categories.filter(id=category.id).exists()
        return False
    
    def is_available_for_business_subcategory(self, subcategory):
        """Check if demo is available for a specific business subcategory"""
        if self.is_for_all_business_subcategories:
            return True
        if subcategory:
            return self.target_business_subcategories.filter(id=subcategory.id).exists()
        return False
    
    def is_available_for_business(self, category=None, subcategory=None):
        """Check if demo is available for given business category/subcategory combination"""
        # If demo has no restrictions, it's available for all
        if self.is_for_all_business_categories and self.is_for_all_business_subcategories:
            return True
        
        # Check category availability
        category_match = self.is_available_for_business_category(category)
        
        # Check subcategory availability
        subcategory_match = self.is_available_for_business_subcategory(subcategory)
        
        # Demo is available if it matches either category or subcategory (or both)
        return category_match or subcategory_match
    
    # Customer Access Control Methods
    @property
    def is_for_all_customers(self):
        return self.target_customers.count() == 0
    
    def can_customer_access(self, customer):
        if self.is_for_all_customers:
            return True
        return self.target_customers.filter(id=customer.id).exists()
    
    # Helper property to get primary business category for display
    @property
    def primary_business_category(self):
        """Get the first business category for display purposes"""
        return self.target_business_categories.first()
    
    @property
    def business_categories_display(self):
        """Get comma-separated list of business categories"""
        categories = self.target_business_categories.all()
        if categories:
            return ", ".join([cat.name for cat in categories])
        return "All Categories"

class DemoView(models.Model):
    """Track demo views by users"""
    
    demo = models.ForeignKey(Demo, on_delete=models.CASCADE, related_name='demo_views')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demo_views')
    viewed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    watch_duration = models.DurationField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'demo_views'
        verbose_name = 'Demo View'
        verbose_name_plural = 'Demo Views'
        unique_together = ['demo', 'user']
        ordering = ['-viewed_at']

class DemoLike(models.Model):
    """Track demo likes by users"""
    
    demo = models.ForeignKey(Demo, on_delete=models.CASCADE, related_name='demo_likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demo_likes')
    liked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'demo_likes'
        verbose_name = 'Demo Like'
        verbose_name_plural = 'Demo Likes'
        unique_together = ['demo', 'user']
        ordering = ['-liked_at']

class DemoFeedback(models.Model):
    """User feedback on demos"""
    
    demo = models.ForeignKey(Demo, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demo_feedbacks')
    
    # Rating & Feedback
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, 
        blank=True,
        verbose_name="Rating (1-5)"
    )
    feedback_text = models.TextField(verbose_name="Feedback")
    
    # Status
    is_approved = models.BooleanField(default=False, verbose_name="Approved")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'demo_feedbacks'
        verbose_name = 'Demo Feedback'
        verbose_name_plural = 'Demo Feedbacks'
        unique_together = ['demo', 'user']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Feedback by {self.user.full_name} on {self.demo.title}"

class TimeSlot(models.Model):
    """Available time slots for demo bookings"""
    
    SLOT_TYPES = [
        ('morning', 'Morning (9:30 AM - 1:00 PM)'),
        ('afternoon', 'Afternoon/Evening (2:00 PM - 7:00 PM)'),
    ]
    
    slot_type = models.CharField(max_length=10, choices=SLOT_TYPES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'time_slots'
        verbose_name = 'Time Slot'
        verbose_name_plural = 'Time Slots'
        ordering = ['start_time']
    
    def __str__(self):
        return f"{self.get_slot_type_display()}: {self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')}"

class DemoRequest(models.Model):
    """User requests for live demo sessions"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rescheduled', 'Rescheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Request Information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demo_requests')
    demo = models.ForeignKey(Demo, on_delete=models.CASCADE, related_name='demo_requests')
    
    # NEW: Business Category Fields
    business_category = models.ForeignKey(
        'accounts.BusinessCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='demo_requests',
        verbose_name="Business Category"
    )
    business_subcategory = models.ForeignKey(
        'accounts.BusinessSubCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='demo_requests',
        verbose_name="Business Subcategory"
    )
    country_region = models.CharField(
        max_length=50, 
        blank=True,  # ✅ Allows empty in forms
        null=True,   # ✅ ADD THIS - Allows NULL in database
        default='IN',  # Optional: default value
        verbose_name="Country/Region"
    )
    
    # Scheduling
    requested_date = models.DateField(verbose_name="Requested Date")
    requested_time_slot = models.ForeignKey(
        TimeSlot, 
        on_delete=models.CASCADE,
        verbose_name="Requested Time Slot"
    )
    
    # Confirmed scheduling
    confirmed_date = models.DateField(null=True, blank=True, verbose_name="Confirmed Date")
    confirmed_time_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='confirmed_requests',
        verbose_name="Confirmed Time Slot"
    )
    
    # Additional Information
    notes = models.TextField(blank=True, verbose_name="Notes/Additional Details")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    postal_code = models.CharField(max_length=20, blank=True, verbose_name="Postal/ZIP Code")
    city = models.CharField(max_length=100, blank=True, verbose_name="City")
    timezone = models.CharField(max_length=50, blank=True, verbose_name="Timezone")
    
    # Geographic metadata
    is_international = models.BooleanField(default=False, verbose_name="International Customer")
    
    # Admin Response
    admin_notes = models.TextField(blank=True, verbose_name="Admin Notes")
    handled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_demo_requests',
        verbose_name="Handled By"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'demo_requests'
        verbose_name = 'Demo Request'
        verbose_name_plural = 'Demo Requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.demo.title} on {self.requested_date}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        # Check if requested date is not Sunday
        if self.requested_date and self.requested_date.weekday() == 6:
            raise ValidationError("Demo requests cannot be made for Sundays.")
        
        # Check if requested date is not in the past
        if self.requested_date and self.requested_date < timezone.now().date():
            raise ValidationError("Demo requests cannot be made for past dates.")
        
        # Validate subcategory belongs to category
        if self.business_subcategory and self.business_category:
            if self.business_subcategory.category != self.business_category:
                raise ValidationError(
                    'Selected subcategory does not belong to the selected category.'
                )
    
    @property
    def effective_date(self):
        return self.confirmed_date or self.requested_date
    
    @property 
    def effective_time_slot(self):
        return self.confirmed_time_slot or self.requested_time_slot