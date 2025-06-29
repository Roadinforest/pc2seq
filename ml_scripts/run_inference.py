import os
import sys

# --- 新的、简单的路径设置 ---
# 将脚本所在的目录（ml_scripts）和其父目录（backend）添加到路径
# 这使得相对导入和绝对导入（从deepcad_lib）都能工作
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

BACKEND_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)
# --- 路径设置结束 ---

import torch
import numpy as np
import argparse
import open3d as o3d
import h5py
import time
import json
from unittest.mock import patch

# 现在，这两种导入方式都应该是稳健的
from extract_commands import get_command_sequence_string # 从同级目录导入
from deepcad_lib.pc2cad import PointNet2
from deepcad_lib.config.configAE import ConfigAE
from deepcad_lib.trainer import TrainerAE

N_POINTS = 2048


def print_status(message):
    """以特定格式打印状态，编码为JSON"""
    print(f"STATUS::{json.dumps({'data': message})}", flush=True)

def print_result(message):
    """将最终结果编码为单行的JSON字符串并打印"""
    print(f"RESULT::{json.dumps({'data': message})}", flush=True)

def print_error(message):
    """打印错误信息，编码为JSON"""
    print(f"ERROR::{json.dumps({'data': message})}", flush=True)


def run_pipeline(ply_file_path, output_dir, pc_model_path, proj_dir, ae_exp_name, ae_ckpt):
    """完整的端到端推理流程"""
    try:
        # --- 步骤 1: 加载和处理点云 ---
        print_status("Step 1/4: Loading and processing point cloud...")
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        pcd = o3d.io.read_point_cloud(ply_file_path)
        if not pcd.has_normals():
            pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))

        points = np.asarray(pcd.points)
        normals = np.asarray(pcd.normals)
        points_with_normals = np.hstack((points, normals))

        # 采样...
        if len(points_with_normals) < N_POINTS:
            indices = np.random.choice(len(points_with_normals), N_POINTS, replace=True)
        else:
            indices = np.random.choice(len(points_with_normals), N_POINTS, replace=False)
        points_sampled = points_with_normals[indices, :]
        points_tensor = torch.tensor(points_sampled, dtype=torch.float32).unsqueeze(0).to(device)
        time.sleep(1)  # 模拟耗时

        # --- 步骤 2: PointNet++ 生成 Z 向量 ---
        print_status("Step 2/4: Generating latent vector with PointNet++...")
        pc_model = PointNet2().to(device)
        checkpoint = torch.load(pc_model_path, map_location=device)
        state_dict = checkpoint.get('model_state_dict', checkpoint)
        pc_model.load_state_dict(state_dict)
        pc_model.eval()
        with torch.no_grad():
            z = pc_model(points_tensor).unsqueeze(1)
        time.sleep(1)  # 模拟耗时

        # --- 步骤 3: DeepCAD Decoder 生成 CAD 向量 ---
        print_status("Step 3/4: Decoding to CAD vector...")
        ae_args_dict = {'proj_dir': proj_dir, 'exp_name': ae_exp_name, 'gpu_ids': '0', 'ckpt': ae_ckpt, 'mode': 'dec'}

        # 使用 patch 来模拟命令行参数
        argv = ['dummy.py'] + [f'--{k}={v}' for k, v in ae_args_dict.items() if v is not None]
        with patch('sys.argv', argv):
            cfg_ae = ConfigAE(phase='test')

        tr_agent = TrainerAE(cfg_ae)
        tr_agent.load_ckpt(cfg_ae.ckpt)
        tr_agent.net.eval()
        with torch.no_grad():
            outputs = tr_agent.decode(z)
            batch_out_vec = tr_agent.logits2vec(outputs)
        cad_vec = batch_out_vec[0]
        time.sleep(1)  # 模拟耗时

        # --- 步骤 4: 提取命令并返回结果 ---
        print_status("Step 4/4: Finalizing and extracting commands...")
        result_string = get_command_sequence_string(cad_vec)

        print_result(result_string)
        print_status("Done.")

    except Exception as e:
        import traceback
        print_error(f"An error occurred during inference: {e}\n{traceback.format_exc()}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ply_file', type=str, required=True)
    parser.add_argument('--output_dir', type=str, required=True)
    # 添加模型路径作为参数，使其更灵活
    parser.add_argument('--pc_model_path', type=str, required=True)
    parser.add_argument('--proj_dir', type=str, required=True)
    parser.add_argument('--ae_exp_name', type=str, required=True)
    parser.add_argument('--ae_ckpt', type=str, required=True)
    args = parser.parse_args()

    run_pipeline(args.ply_file, args.output_dir, args.pc_model_path, args.proj_dir, args.ae_exp_name, args.ae_ckpt)