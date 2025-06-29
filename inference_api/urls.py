# inference_api/urls.py
from django.urls import path
from .views import upload_ply_view, process_ply_view

urlpatterns = [
    path('upload/', upload_ply_view, name='upload_ply'),
    path('process-ply/', process_ply_view, name='process_ply'),
]