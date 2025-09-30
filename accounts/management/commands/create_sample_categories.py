# Create this file: accounts/management/commands/create_sample_categories.py

# First create these directories if they don't exist:
# accounts/management/
# accounts/management/__init__.py
# accounts/management/commands/
# accounts/management/commands/__init__.py

from django.core.management.base import BaseCommand
from accounts.models import BusinessCategory, BusinessSubCategory

class Command(BaseCommand):
    help = 'Create sample business categories and subcategories for Indian businesses'

    def handle(self, *args, **options):
        # Sample categories and subcategories for Indian businesses
        categories_data = {
            'Manufacturing & Production': {
                'icon': '🏭',
                'subcategories': [
                    'Automotive & Auto Components',
                    'Textiles & Apparel',
                    'Electronics & Electrical',
                    'Pharmaceuticals & Healthcare',
                    'Steel & Metal Processing',
                    'Food Processing & Beverages',
                    'Chemicals & Petrochemicals',
                    'Plastic & Packaging',
                    'Cement & Construction Materials',
                    'Paper & Pulp',
                    'Leather & Footwear',
                    'Gems & Jewelry'
                ]
            },
            'Information Technology': {
                'icon': '💻',
                'subcategories': [
                    'Software Development',
                    'IT Services & Consulting',
                    'Product Development',
                    'Mobile App Development',
                    'Web Development',
                    'Data Analytics & Big Data',
                    'Cloud Services',
                    'Cybersecurity',
                    'AI & Machine Learning',
                    'Blockchain Technology',
                    'IoT Solutions',
                    'Enterprise Software'
                ]
            },
            'Healthcare & Life Sciences': {
                'icon': '🏥',
                'subcategories': [
                    'Hospitals & Healthcare',
                    'Clinics & Diagnostic Centers',
                    'Medical Equipment & Devices',
                    'Pharmaceuticals',
                    'Biotechnology',
                    'Telemedicine',
                    'Health Insurance',
                    'Medical Software & Apps',
                    'Medical Research',
                    'Ayurveda & Traditional Medicine'
                ]
            },
            'Financial Services': {
                'icon': '🏦',
                'subcategories': [
                    'Banking & Credit',
                    'Insurance Services',
                    'Investment & Wealth Management',
                    'Mutual Funds',
                    'Credit Cards & Payment Solutions',
                    'Loans & Microfinance',
                    'Fintech & Digital Payments',
                    'Stock Broking',
                    'Asset Management',
                    'Financial Planning'
                ]
            },
            'Retail & E-commerce': {
                'icon': '🛒',
                'subcategories': [
                    'Online Marketplace',
                    'Fashion & Lifestyle',
                    'Electronics & Gadgets',
                    'Grocery & FMCG',
                    'Beauty & Personal Care',
                    'Sports & Fitness',
                    'Home & Kitchen',
                    'Books & Media',
                    'Furniture & Decor',
                    'Automotive Retail'
                ]
            },
            'Education & Training': {
                'icon': '📚',
                'subcategories': [
                    'Schools & K-12 Education',
                    'Higher Education & Universities',
                    'Online Learning Platforms',
                    'Coaching & Test Preparation',
                    'Skill Development & Vocational Training',
                    'Corporate Training',
                    'EdTech Solutions',
                    'Language Learning',
                    'Professional Certification',
                    'Early Childhood Education'
                ]
            },
            'Real Estate & Construction': {
                'icon': '🏢',
                'subcategories': [
                    'Residential Real Estate',
                    'Commercial Real Estate',
                    'Property Management',
                    'Construction & Infrastructure',
                    'Interior Design',
                    'Real Estate Services',
                    'Property Investment',
                    'PropTech Solutions',
                    'Architecture & Planning',
                    'Building Materials'
                ]
            },
            'Transportation & Logistics': {
                'icon': '🚛',
                'subcategories': [
                    'Freight & Cargo',
                    'Last Mile Delivery',
                    'Warehousing & Storage',
                    'Fleet Management',
                    'Supply Chain Solutions',
                    'Courier & Express Services',
                    'Transportation Technology',
                    'Port & Airport Services',
                    'Railway Services',
                    'Aviation Services'
                ]
            },
            'Food & Hospitality': {
                'icon': '🍽️',
                'subcategories': [
                    'Restaurants & QSR',
                    'Food Delivery Services',
                    'Catering Services',
                    'Food Manufacturing',
                    'Beverage Industry',
                    'Cloud Kitchen',
                    'Food Technology',
                    'Organic & Health Foods',
                    'Hotels & Accommodation',
                    'Travel & Tourism'
                ]
            },
            'Media & Entertainment': {
                'icon': '🎬',
                'subcategories': [
                    'Digital Media & Content',
                    'Advertising & Marketing',
                    'Gaming & Esports',
                    'Movies & Television',
                    'Music & Audio',
                    'Publishing & Print Media',
                    'Event Management',
                    'Content Creation',
                    'Social Media Marketing',
                    'Influencer Marketing'
                ]
            },
            'Agriculture & Rural': {
                'icon': '🌾',
                'subcategories': [
                    'Crop Production & Farming',
                    'Dairy & Animal Husbandry',
                    'AgriTech Solutions',
                    'Food Processing & Supply Chain',
                    'Agricultural Equipment',
                    'Organic Farming',
                    'Agricultural Finance',
                    'Farm Management Technology',
                    'Seeds & Fertilizers',
                    'Rural Development'
                ]
            },
            'Energy & Environment': {
                'icon': '⚡',
                'subcategories': [
                    'Solar Energy',
                    'Wind Energy',
                    'Oil & Gas',
                    'Power Generation & Distribution',
                    'Energy Storage Solutions',
                    'Green Technology',
                    'Energy Efficiency',
                    'Renewable Energy',
                    'Environmental Services',
                    'Waste Management'
                ]
            },
            'Professional Services': {
                'icon': '💼',
                'subcategories': [
                    'Legal Services',
                    'Accounting & Taxation',
                    'Management Consulting',
                    'HR & Recruitment',
                    'Marketing & Advertising',
                    'Business Process Outsourcing',
                    'Design & Creative Services',
                    'Research & Analytics',
                    'Quality Assurance & Testing',
                    'Project Management'
                ]
            },
            'Telecommunications': {
                'icon': '📡',
                'subcategories': [
                    'Mobile Network Operators',
                    'Internet Service Providers',
                    'Telecom Equipment',
                    'Satellite Communications',
                    'Network Infrastructure',
                    'VoIP & Communication Services',
                    '5G Technology',
                    'Broadband Services',
                    'Telecom Software',
                    'Digital Communication'
                ]
            },
            'Government & Public Sector': {
                'icon': '🏛️',
                'subcategories': [
                    'Central Government',
                    'State Government',
                    'Local Government & Municipalities',
                    'Public Sector Enterprises',
                    'Defense & Security',
                    'Public Services',
                    'Government Technology',
                    'Policy & Regulatory',
                    'Public Infrastructure',
                    'Social Services'
                ]
            }
        }

        # Create categories and subcategories
        created_categories = 0
        created_subcategories = 0
        
        for category_name, category_data in categories_data.items():
            # Create or get category
            category, created = BusinessCategory.objects.get_or_create(
                name=category_name,
                defaults={
                    'description': f'{category_name} industry businesses and services',
                    'icon': category_data.get('icon', '🏢'),
                    'is_active': True,
                    'sort_order': created_categories
                }
            )
            
            if created:
                created_categories += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created category: {category_name}')
                )
            else:
                self.stdout.write(f'  Category already exists: {category_name}')
            
            # Create subcategories
            for i, subcategory_name in enumerate(category_data['subcategories']):
                subcategory, sub_created = BusinessSubCategory.objects.get_or_create(
                    category=category,
                    name=subcategory_name,
                    defaults={
                        'description': f'{subcategory_name} services and solutions',
                        'is_active': True,
                        'sort_order': i
                    }
                )
                
                if sub_created:
                    created_subcategories += 1
                    self.stdout.write(f'    → Created subcategory: {subcategory_name}')

        # Summary
        total_categories = BusinessCategory.objects.count()
        total_subcategories = BusinessSubCategory.objects.count()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 SUMMARY:'
                f'\n   • Created {created_categories} new categories'
                f'\n   • Created {created_subcategories} new subcategories'
                f'\n   • Total categories: {total_categories}'
                f'\n   • Total subcategories: {total_subcategories}'
                f'\n\n✅ Business categories setup completed successfully!'
            )
        )

# To run this command:
# python manage.py create_sample_categories