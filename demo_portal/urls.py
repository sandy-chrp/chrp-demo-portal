# demo_portal/urls.py (Fixed - No duplicate namespaces)
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

handler404 = 'core.views.custom_404'
handler500 = 'core.views.custom_500'

urlpatterns = [
    # Django's default admin (for development only)
    path('django-admin/', admin.site.urls),
    
    # Customer Portal URLs (Landing page, dashboard, contact)
    path('', include('core.urls')),
    
    # Authentication URLs
    path('auth/', include('accounts.urls')),
    
    # Feature URLs  
    path('demos/', include('demos.urls')),
    path('enquiries/', include('enquiries.urls')),
    path('notifications/', include(('notifications.urls', 'notifications'), namespace='notifications')),
    path('chatbot/', include('chatbot.urls')),
    path('customer/', include('customers.urls')),

]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)