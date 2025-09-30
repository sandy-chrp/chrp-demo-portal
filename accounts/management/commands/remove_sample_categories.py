# accounts/management/commands/remove_sample_categories.py
from django.core.management.base import BaseCommand
from accounts.models import BusinessCategory, BusinessSubCategory

class Command(BaseCommand):
    help = 'Remove all sample business categories and subcategories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompting',
        )

    def handle(self, *args, **options):
        # Count existing data
        total_categories = BusinessCategory.objects.count()
        total_subcategories = BusinessSubCategory.objects.count()
        
        if total_categories == 0 and total_subcategories == 0:
            self.stdout.write(
                self.style.WARNING('No business categories or subcategories found to delete.')
            )
            return
        
        # Show what will be deleted
        self.stdout.write(
            self.style.WARNING(
                f'\n⚠️  WARNING: This will delete:'
                f'\n   • {total_categories} Business Categories'
                f'\n   • {total_subcategories} Business Subcategories'
            )
        )
        
        # Check if any customers are using these categories
        categories_with_customers = BusinessCategory.objects.filter(
            customers__isnull=False
        ).distinct().count()
        
        subcategories_with_customers = BusinessSubCategory.objects.filter(
            customers__isnull=False
        ).distinct().count()
        
        if categories_with_customers > 0 or subcategories_with_customers > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'\n❌ ERROR: Cannot delete!'
                    f'\n   • {categories_with_customers} categories have customers'
                    f'\n   • {subcategories_with_customers} subcategories have customers'
                    f'\n\nPlease reassign customers first before deleting.'
                )
            )
            return
        
        # Ask for confirmation
        if not options['confirm']:
            confirm = input('\nType "DELETE" to confirm deletion: ')
            if confirm != 'DELETE':
                self.stdout.write(self.style.WARNING('Deletion cancelled.'))
                return
        
        # Delete subcategories first
        deleted_subcategories, _ = BusinessSubCategory.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f'✓ Deleted {total_subcategories} subcategories')
        )
        
        # Delete categories
        deleted_categories, _ = BusinessCategory.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(f'✓ Deleted {total_categories} categories')
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Successfully removed all business categories and subcategories!'
            )
        )

# To run this command:
# python manage.py remove_sample_categories
# 
# Or without confirmation prompt:
# python manage.py remove_sample_categories --confirm