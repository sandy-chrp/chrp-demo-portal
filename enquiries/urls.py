from django.urls import path
from . import views

app_name = 'enquiries'

urlpatterns = [
    path('', views.enquiry_list_view, name='list'),
    path('send/', views.send_enquiry_view, name='send'),
    path('<int:enquiry_id>/', views.enquiry_detail_view, name='detail'),
]