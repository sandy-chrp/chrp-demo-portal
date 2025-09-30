from django.shortcuts import render

def enquiry_list_view(request):
    return render(request, 'enquiries/list.html', {})

def send_enquiry_view(request):
    return render(request, 'enquiries/send.html', {})

def enquiry_detail_view(request, enquiry_id):
    return render(request, 'enquiries/detail.html', {})