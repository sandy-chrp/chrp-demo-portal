# core/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class SiteSettings(models.Model):
    """Site-wide settings and configuration"""
    
    # Site Information
    site_name = models.CharField(max_length=100, default="Demo Portal")
    site_description = models.TextField(default="Professional Business Demo Portal - CHRP India")
    site_logo = models.ImageField(upload_to='site/', null=True, blank=True)
    favicon = models.ImageField(upload_to='site/', null=True, blank=True)
    
    # Contact Information
    contact_email = models.EmailField(default="support@chrp-india.com")
    contact_phone = models.CharField(max_length=20, default="+91-1234567890")
    address = models.TextField(blank=True)
    
    # Social Media
    facebook_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    
    # Demo Settings
    max_demo_requests_per_day = models.PositiveIntegerField(default=3)
    demo_booking_advance_days = models.PositiveIntegerField(default=30)
    auto_approve_demo_requests = models.BooleanField(default=False)
    
    # Email Settings
    welcome_email_enabled = models.BooleanField(default=True)
    notification_emails_enabled = models.BooleanField(default=True)
    
    # Maintenance
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'site_settings'
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'
    
    def __str__(self):
        return self.site_name
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def load(cls):
        """Load site settings (create if doesn't exist)"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

class ContactMessage(models.Model):
    """Contact form messages from landing page"""
    
    # Contact Information
    name = models.CharField(max_length=100, verbose_name="Name")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Phone")
    company = models.CharField(max_length=200, blank=True, verbose_name="Company")
    
    # Message
    subject = models.CharField(max_length=200, verbose_name="Subject")
    message = models.TextField(verbose_name="Message")
    
    # Tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Status
    is_read = models.BooleanField(default=False, verbose_name="Read")
    is_responded = models.BooleanField(default=False, verbose_name="Responded")
    
    # Admin Response
    admin_notes = models.TextField(blank=True, verbose_name="Admin Notes")
    responded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_responses',
        verbose_name="Responded By"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'contact_messages'
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.subject}"