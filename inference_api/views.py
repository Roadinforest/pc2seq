# backend/inference_api/views.py
from django.http import JsonResponse, StreamingHttpResponse
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from rest_framework.decorators import api_view
import threading
import subprocess
import os
import json
import uuid
import time
import sys
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view, parser_classes
from django.http import JsonResponse, StreamingHttpResponse

# 全局锁，确保一次只有一个推理任务在GPU上运行
inference_lock = threading.Lock()


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser]) # 明确告诉 DRF 我们要处理文件上传
def upload_ply_view(request):
    if 'file' not in request.data:
        return JsonResponse({'error': 'No file provided'}, status=400)

    file = request.data['file']

    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads'))
    file_extension = os.path.splitext(file.name)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    filename = fs.save(unique_filename, file)

    return JsonResponse({'file_id': filename})


def stream_inference_response(ply_filename):
    """生成器函数，用于流式传输推理过程的响应（增强诊断版）"""

    # 立即发送一个连接成功的消息
    connect_message = json.dumps({'type': 'status', 'data': 'Connection established. Awaiting GPU allocation...'})
    yield f"data: {connect_message}\n\n"

    # 尝试获取锁
    if not inference_lock.acquire(blocking=False):
        time.sleep(0.1)
        error_message = json.dumps({'type': 'error', 'data': 'GPU is busy. Please try again later.'})
        yield f"data: {error_message}\n\n"
        return

    """生成器函数..."""
    # ... (心跳和锁) ...
    try:
        PROJECT_ROOT = settings.BASE_DIR.parent
        ply_filepath = os.path.join(PROJECT_ROOT, 'media', 'uploads', ply_filename)
        pc_model_path = os.path.join(PROJECT_ROOT, 'pc2seq/deepcad_lib/Point++', 'latest.pth')
        proj_dir = os.path.join(PROJECT_ROOT, 'pc2seq/deepcad_lib/proj_log')

        # --- 关键修改：设置子进程的工作目录 ---
        # 我们让子进程在 'backend' 目录下运行
        backend_dir = str(settings.BASE_DIR)

        # ml_script_path 现在可以是相对于 cwd 的路径
        ml_script_name = 'run_inference.py'
        ml_script_path = os.path.join('ml_scripts', ml_script_name)

        python_executable = sys.executable

        command = [
            python_executable, '-u', ml_script_path,
            '--ply_file', ply_filepath,
            '--output_dir', os.path.join(PROJECT_ROOT, 'media', 'results'),
            '--pc_model_path', pc_model_path,
            '--proj_dir', proj_dir,
            '--ae_exp_name', 'pretrained',
            '--ae_ckpt', '1000',
        ]

        # --- 关键修改：在 Popen 中使用 cwd ---
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8',
            cwd=backend_dir  # <-- 设置子进程的工作目录为 backend/
        )

        for line in iter(process.stdout.readline, ''):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 检查消息头
            if line_stripped.startswith('STATUS::'):
                data_json = line_stripped[len('STATUS::'):]
                message = json.dumps({'type': 'status', **json.loads(data_json)})
                yield f"data: {message}\n\n"

            elif line_stripped.startswith('RESULT::'):
                data_json = line_stripped[len('RESULT::'):]
                message = json.dumps({'type': 'result', **json.loads(data_json)})
                yield f"data: {message}\n\n"

            elif line_stripped.startswith('ERROR::'):
                data_json = line_stripped[len('ERROR::'):]
                message = json.dumps({'type': 'error', **json.loads(data_json)})
                yield f"data: {message}\n\n"

            else:  # 捕获任何其他未标记的日志，用于调试
                message = json.dumps({'type': 'status', 'data': f"SCRIPT_LOG: {line_stripped}"})
                yield f"data: {message}\n\n"

        process.wait()

        if process.returncode != 0:
            error_message = json.dumps(
                {'type': 'error', 'data': f"Inference script exited with a non-zero code: {process.returncode}."})
            yield f"data: {error_message}\n\n"

    finally:
        inference_lock.release()
        close_message = json.dumps({'type': 'status', 'data': 'Stream closed.'})
        yield f"data: {close_message}\n\n"



def process_ply_view(request):  # <--- 不再需要 @api_view(['GET'])
    """处理SSE请求，现在是一个纯粹的 Django 视图"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Only GET requests are allowed'}, status=405)

    file_id = request.GET.get('file_id')
    if not file_id:
        return JsonResponse({'error': 'No file_id provided'}, status=400)

    # 检查文件是否存在
    ply_filepath = os.path.join(settings.MEDIA_ROOT, 'uploads', file_id)
    if not os.path.exists(ply_filepath):
        return JsonResponse({'error': 'File not found'}, status=404)

    response = StreamingHttpResponse(stream_inference_response(file_id), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    return response