from django.shortcuts import render
from django.http import JsonResponse

def notification_list_view(request):
    return render(request, 'notifications/list.html', {})

def mark_as_read_view(request, notification_id):
    return JsonResponse({'success': True})

def mark_all_as_read_view(request):
    return JsonResponse({'success': True})