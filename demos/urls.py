from django.urls import path
from . import views

app_name = 'demos'

urlpatterns = [
    path('', views.demo_list_view, name='list'),
    path('request/', views.request_demo_view, name='request'),  # General request form
    path('requests/my/', views.my_demo_requests_view, name='my_requests'),
    path('<slug:slug>/', views.demo_detail_view, name='detail'),
    path('<slug:slug>/watch/', views.watch_demo_view, name='watch'),
    path('<slug:slug>/like/', views.like_demo_view, name='like'),
    path('<slug:slug>/feedback/', views.demo_feedback_view, name='feedback'),
    path('<slug:slug>/request/', views.request_demo_view, name='request_specific'),  # Request specific demo
]