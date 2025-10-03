from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
import json

from demos.models import DemoRequest

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def cancel_demo_request(request, request_id):
    """Cancel a demo request with reason"""
    if not request.user.is_approved:
        return JsonResponse({'success': False, 'error': 'Not authorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '').strip()
        details = data.get('details', '').strip()
        
        if not reason:
            return JsonResponse({'success': False, 'error': 'Reason is required'}, status=400)
        
        demo_request = get_object_or_404(
            DemoRequest,
            id=request_id,
            user=request.user
        )
        
        # Only allow cancellation if pending or confirmed
        if demo_request.status not in ['pending', 'confirmed']:
            return JsonResponse({
                'success': False,
                'error': 'Can only cancel pending or confirmed requests'
            }, status=400)
        
        # Update status
        demo_request.status = 'cancelled'
        
        # Map reason codes to readable labels
        reason_labels = {
            'scheduling_conflict': 'Scheduling Conflict / Availability Issues',
            'requirements_change': 'Change in Project Requirements',
            'found_alternative': 'Found Alternative Solution',
            'no_longer_interested': 'No Longer Interested',
            'demo_not_relevant': 'Demo Not Relevant',
            'other': 'Other Reasons'
        }
        
        # Get readable reason text
        reason_text = reason_labels.get(reason, reason)
        
        # Add cancellation info to admin notes
        cancel_info = f"[CANCELLED BY CUSTOMER]\nReason: {reason_text}"
        if details:
            cancel_info += f"\nDetails: {details}"
        cancel_info += f"\nCancelled at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        if demo_request.admin_notes:
            demo_request.admin_notes += f"\n\n{cancel_info}"
        else:
            demo_request.admin_notes = cancel_info
        
        demo_request.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Demo request cancelled successfully'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)