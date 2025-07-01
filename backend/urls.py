"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# backend/urls.py
from django.contrib import admin
from django.urls import path, include # 确保导入了 include
from django.conf import settings
from django.conf.urls.static import static
from inference_api.views import upload_ply_view, process_ply_view


# urlpatterns = [
#     path('admin/', admin.site.urls),
#     # 将所有 /api/ 开头的请求，都转发到 inference_api.urls 文件去处理
#     path('api/', include('inference_api.urls')),
# ]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/upload/', upload_ply_view, name='upload_ply'),
    path('api/process-ply/', process_ply_view, name='process_ply'),
]

# (新增) 在开发模式下，让 Django 处理媒体文件的访问
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)