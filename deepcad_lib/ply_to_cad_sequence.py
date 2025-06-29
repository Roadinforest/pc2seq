# ply_to_cad_sequence.py (Final, correct version)

import torch
import numpy as np
import argparse
import os
import random
import open3d as o3d
# 新增导入
import h5py

# --- 关键代码导入 ---
from pc2cad import PointNet2, read_ply
from config.configAE import ConfigAE
from trainer import TrainerAE
from cadlib.macro import EOS_IDX

N_POINTS = 2048


def main(args):

    device = torch.device(f"cuda:{args.gpu_ids}" if torch.cuda.is_available() else "cpu")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_ids)
    print(f"Using device: {device}")

    # --- 步骤 1: 加载点云并计算法向量 ---
    print("\n--- Step 1: Loading, processing point cloud, and estimating normals ---")
    if not os.path.exists(args.ply_file):
        raise FileNotFoundError(f"PLY file not found at: {args.ply_file}")
    pcd = o3d.io.read_point_cloud(args.ply_file)
    print(f"Loaded {len(pcd.points)} points from {args.ply_file}")
    if not pcd.has_normals():
        print("Point cloud does not have normals. Estimating normals...")
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        print("Normals estimated.")
    else:
        print("Point cloud has existing normals.")
    points = np.asarray(pcd.points)
    normals = np.asarray(pcd.normals)
    points_with_normals = np.hstack((points, normals))
    if points_with_normals.shape[0] < N_POINTS:
        indices = np.random.choice(points_with_normals.shape[0], N_POINTS, replace=True)
    else:
        indices = np.random.choice(points_with_normals.shape[0], N_POINTS, replace=False)
    points_sampled = points_with_normals[indices, :]
    points_tensor = torch.tensor(points_sampled, dtype=torch.float32).unsqueeze(0).to(device)
    print(f"Point cloud (with normals) sampled and converted to tensor with shape: {points_tensor.shape}")

    # --- 步骤 2: 使用PointNet++模型生成潜在向量 z ---
    print("\n--- Step 2: Generating latent vector (z) using PointNet++ ---")
    pc_model = PointNet2().to(device)
    print(f"Loading PointNet++ model from: {args.pc_model_path}")
    try:
        checkpoint = torch.load(args.pc_model_path, map_location=device)
        if isinstance(checkpoint, dict):
            state_dict = checkpoint.get('model_state_dict') or checkpoint.get('net_state') or checkpoint
        else:
            state_dict = checkpoint
        pc_model.load_state_dict(state_dict)
        print("Successfully loaded PointNet++ model state.")
    except Exception as e:
        print(f"\nError loading PointNet++ model: {e}")
        return
    pc_model.eval()
    with torch.no_grad():
        z = pc_model(points_tensor)
    z = z.unsqueeze(1)
    print(f"Generated latent vector z with shape: {z.shape}")

    # --- 步骤 3: 使用DeepCAD解码器生成CAD序列 ---
    print("\n--- Step 3: Decoding z to CAD vector using DeepCAD Decoder ---")
    store_true_flags = ['continue', 'vis', 'augment']
    ae_args_dict = {'proj_dir': args.proj_dir, 'exp_name': args.ae_exp_name, 'gpu_ids': args.gpu_ids,
                    'ckpt': args.ae_ckpt, 'mode': 'dec', 'outputs': None, 'z_path': None, 'continue': False,
                    'vis': False, 'augment': False}
    from unittest.mock import patch
    argv = ['test.py']
    for k, v in ae_args_dict.items():
        if k in store_true_flags:
            if v: argv.append(f'--{k}')
        elif v is not None:
            argv.extend([f'--{k}', str(v)])
    print(f"Mocking sys.argv with: {argv}")
    with patch('sys.argv', argv):
        cfg_ae = ConfigAE(phase='test')
    tr_agent = TrainerAE(cfg_ae)
    tr_agent.load_ckpt(cfg_ae.ckpt)
    tr_agent.net.eval()
    print(f"Loaded DeepCAD AE model from experiment '{args.ae_exp_name}' with checkpoint '{cfg_ae.ckpt}'.")
    with torch.no_grad():
        outputs = tr_agent.decode(z)
        batch_out_vec = tr_agent.logits2vec(outputs)
    cad_vec = batch_out_vec[0]
    print(f"Decoded to CAD vector with shape: {cad_vec.shape}")

    # --- 步骤 4: 将原始CAD向量保存为H5文件 ---
    print("\n--- Step 4: Saving raw CAD vector to H5 file ---")

    # 找到序列的实际结束位置
    try:
        # np.where returns a tuple of arrays, one for each dimension
        eos_indices = np.where(cad_vec[:, 0] == EOS_IDX)[0]
        if len(eos_indices) > 0:
            seq_len = eos_indices[0]
            # 截取到EOS之前（不包括EOS，因为vec2CADsolid可能不需要它）
            cad_vec_trimmed = cad_vec[:seq_len]
            print(f"Original sequence length: {len(cad_vec)}, trimmed to: {len(cad_vec_trimmed)}")
        else:
            cad_vec_trimmed = cad_vec
            print("Warning: EOS token not found in the sequence.")
    except Exception as e:
        print(f"Could not trim sequence, using full vector. Error: {e}")
        cad_vec_trimmed = cad_vec

    # 确定输出路径
    os.makedirs(args.output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(args.ply_file))[0]
    output_path = os.path.join(args.output_dir, f"{base_name}_reconstructed.h5")

    # 保存为 H5 文件
    with h5py.File(output_path, 'w') as f:
        # 保存为 'out_vec'，这是 show.py 所期望的键名
        f.create_dataset('out_vec', data=cad_vec_trimmed, dtype=np.int32)

    print(f"\nSuccessfully saved the reconstructed CAD vector to: {output_path}")
    print(f"You can now visualize this file using:\npython utils/show.py --src {args.output_dir} --form h5")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Convert a .ply file to a CAD vector and save as .h5.")

    parser.add_argument('--ply_file', type=str, required=True, help="Path to the input .ply point cloud file.")
    parser.add_argument('--pc_model_path', type=str, default='latest.pth',
                        help="Path to the pre-trained PointNet++ model checkpoint (.pth).")
    parser.add_argument('--proj_dir', type=str, default="proj_log",
                        help="Path to project folder where AE models are saved.")
    parser.add_argument('--ae_exp_name', type=str, required=True, help="Name of the Autoencoder experiment.")
    parser.add_argument('--ae_ckpt', type=str, default='latest', required=False,
                        help="Desired AE checkpoint to restore (e.g., 'latest', '1000').")
    parser.add_argument('-o', '--output_dir', type=str, default='./reconstructions',
                        help="Directory to save the output .h5 file.")
    parser.add_argument('-g', '--gpu_ids', type=str, default='0', help="GPU to use, e.g. '0'.")

    args = parser.parse_args()
    main(args)