# notifications/management/commands/init_notifications.py
from django.core.management.base import BaseCommand
from notifications.models import NotificationTemplate


class Command(BaseCommand):
    help = 'Initialize notification templates'
    
    def handle(self, *args, **options):
        templates = [
            {
                'name': 'Account Approved',
                'notification_type': 'account_approved',
                'email_subject': 'Welcome! Your Account is Approved',
                'email_body': '''
                    <h2>Welcome to CHRP India!</h2>
                    <p>Dear {{user_name}},</p>
                    <p>Your account has been approved on {{approval_date}}.</p>
                    <p>You now have full access to our demo portal.</p>
                ''',
                'title_template': 'Account Approved!',
                'message_template': 'Your account has been approved on {{approval_date}}',
            },
            # ... add other templates from your utils file
        ]
        
        for data in templates:
            NotificationTemplate.objects.get_or_create(
                notification_type=data['notification_type'],
                defaults=data
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Created {len(templates)} notification templates')
        )