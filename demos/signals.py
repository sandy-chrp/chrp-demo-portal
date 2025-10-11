# demos/signals.py
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from .models import Demo
import os
import shutil
from django.conf import settings

@receiver(pre_delete, sender=Demo)
def cleanup_demo_files(sender, instance, **kwargs):
    """Clean up extracted WebGL files when demo is deleted"""
    if instance.extracted_path:
        extract_dir = os.path.join(settings.MEDIA_ROOT, instance.extracted_path)
        if os.path.exists(extract_dir):
            try:
                shutil.rmtree(extract_dir)
            except Exception as e:
                print(f"Error cleaning up extracted files: {e}")

@receiver(pre_save, sender=Demo)
def cleanup_old_extracted_files(sender, instance, **kwargs):
    """Clean up old extracted files when WebGL file is changed"""
    if instance.pk:
        try:
            old_demo = Demo.objects.get(pk=instance.pk)
            if old_demo.webgl_file != instance.webgl_file and old_demo.extracted_path:
                extract_dir = os.path.join(settings.MEDIA_ROOT, old_demo.extracted_path)
                if os.path.exists(extract_dir):
                    shutil.rmtree(extract_dir)
        except Demo.DoesNotExist:
            pass