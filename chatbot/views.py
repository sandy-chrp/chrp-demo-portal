# chatbot/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
import json

def chatbot_interface(request):
    """Chatbot interface view"""
    return JsonResponse({
        'status': 'ready',
        'message': 'Chatbot is ready to help!'
    })

@csrf_exempt
@require_http_methods(["POST"])
def chat_message(request):
    """Handle chatbot messages"""
    try:
        data = json.loads(request.body)
        message = data.get('message', '').lower().strip()
        
        # Basic FAQ responses
        if not message:
            response = "Hi! I'm here to help you. You can ask me about demos, account issues, pricing, or anything else!"
        elif any(word in message for word in ['demo', 'video', 'watch']):
            response = "You can watch demos from your dashboard or request live demo sessions. Would you like me to show you how to access them?"
        elif any(word in message for word in ['contact', 'support', 'help']):
            response = "You can reach our support team at support@chrp-india.com or use the contact form. Need immediate assistance? I can connect you with our admin team."
        elif any(word in message for word in ['account', 'login', 'signup', 'register']):
            response = "For account issues: Login problems? Try password reset. New user? Sign up with your business email. Account pending? Admin approval takes 24-48 hours."
        elif any(word in message for word in ['price', 'cost', 'pricing', 'money']):
            response = "Our solutions are customized for each business. Would you like to connect with our sales team for detailed pricing information?"
        elif any(word in message for word in ['enquiry', 'inquiry', 'question', 'business']):
            response = "You can send business enquiries from your dashboard and track their status. What specific information do you need?"
        elif any(word in message for word in ['time', 'schedule', 'booking', 'appointment']):
            response = "Demo sessions can be booked: Morning (9:30 AM - 1:00 PM) or Afternoon (2:00 PM - 7:00 PM). Not available on Sundays."
        elif any(word in message for word in ['thank', 'thanks', 'appreciate']):
            response = "You're welcome! I'm happy to help. Is there anything else you'd like to know?"
        elif any(word in message for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            response = "Hello! Welcome to Demo Portal. I'm here to assist you with demos, account questions, and more. What can I help you with today?"
        else:
            response = "I'm here to help! You can ask me about:\n• Demo videos and live sessions\n• Account and login issues\n• Pricing information\n• Business enquiries\n• Scheduling appointments\n• Contact information\n\nWhat would you like to know?"
        
        return JsonResponse({
            'success': True,
            'response': response,
            'timestamp': str(timezone.now()) if 'timezone' in globals() else None
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'response': "Sorry, I'm having trouble understanding. Please try again or contact our support team at support@chrp-india.com"
        })

def get_faqs(request):
    """Get frequently asked questions"""
    faqs = [
        {
            "question": "How do I watch demos?", 
            "answer": "Go to your dashboard and browse available demos by category. Click on any demo to watch it instantly."
        },
        {
            "question": "How do I request a live demo?", 
            "answer": "Click 'Request Demo' on any video and choose your preferred time slot. Available times: Morning (9:30 AM - 1:00 PM) or Afternoon (2:00 PM - 7:00 PM)."
        },
        {
            "question": "How do I contact support?", 
            "answer": "Email us at support@chrp-india.com, use this chat to connect with admin, or visit our contact page."
        },
        {
            "question": "When will my account be approved?", 
            "answer": "Account approval typically takes 24-48 hours during business days. You'll receive an email notification once approved."
        },
        {
            "question": "What are your business hours?", 
            "answer": "Demo sessions: Monday-Saturday, 9:30 AM - 7:00 PM (closed Sundays). Support: Monday-Friday, 9:00 AM - 6:00 PM."
        },
        {
            "question": "How do I send a business enquiry?", 
            "answer": "Use the 'Send Enquiry' option in your dashboard. Fill in your business details and query - our team will respond within 24 hours."
        },
        {
            "question": "Can I reschedule a demo appointment?", 
            "answer": "Yes! Contact our support team or check your dashboard for rescheduling options. We'll help you find a new suitable time."
        }
    ]
    
    return JsonResponse({'faqs': faqs})

@login_required
def connect_to_admin(request):
    """Connect user to admin/support"""
    user = request.user
    
    # Log the admin connection request (you could save to database)
    # AdminConnectionRequest.objects.create(user=user, ...)
    
    return JsonResponse({
        'success': True,
        'message': f'Hi {user.first_name}! I\'m connecting you to our support team. They will reach out to you shortly.',
        'contact_email': 'support@chrp-india.com',
        'contact_phone': '+91-1234567890',
        'user_info': {
            'name': user.full_name,
            'email': user.email,
            'organization': user.organization
        }
    })

@csrf_exempt 
@require_http_methods(["POST"])
def quick_actions(request):
    """Handle quick action requests from chatbot"""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        
        if action == 'show_demos':
            return JsonResponse({
                'success': True,
                'message': 'Redirecting you to demo library...',
                'redirect_url': '/demos/'
            })
        elif action == 'contact_sales':
            return JsonResponse({
                'success': True,
                'message': 'Opening sales contact form...',
                'redirect_url': '/contact-sales/'
            })
        elif action == 'my_account':
            return JsonResponse({
                'success': True,
                'message': 'Taking you to your profile...',
                'redirect_url': '/auth/profile/'
            })
        elif action == 'send_enquiry':
            return JsonResponse({
                'success': True,
                'message': 'Opening enquiry form...',
                'redirect_url': '/enquiries/send/'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Unknown action requested.'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Sorry, something went wrong with that action.'
        })