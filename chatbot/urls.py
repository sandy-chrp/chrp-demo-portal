# chatbot/urls.py
from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    # Chatbot Interface
    path('', views.chatbot_interface, name='interface'),
    path('chat/', views.chat_message, name='chat'),
    path('faqs/', views.get_faqs, name='faqs'),
    path('connect-admin/', views.connect_to_admin, name='connect_admin'),
    path('quick-actions/', views.quick_actions, name='quick_actions'),
]