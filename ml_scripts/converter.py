# backend/ml_scripts/converter.py
import os
import h5py
import numpy as np
from cadlib.visualize import vec2CADsolid
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Extend.DataExchange import write_step_file


def h5_to_step(h5_path, output_step_path):
    """
    尝试将 H5 文件中的 'out_vec' 转换为 STEP 文件。
    如果成功，返回 True。
    如果失败，抛出异常。
    """
    try:
        with h5py.File(h5_path, 'r') as fp:
            out_vec = fp["out_vec"][:].astype(np.float64)
            # 核心转换步骤
            out_shape = vec2CADsolid(out_vec)
    except Exception as e:
        # 在向量到实体转换时失败
        raise ValueError(f"Failed to create 3D solid from vector. Reason: {e}")

    if out_shape is None:
        raise ValueError("vec2CADsolid returned a null shape.")

    # 可选但推荐：检查生成的实体是否有效
    analyzer = BRepCheck_Analyzer(out_shape)
    if not analyzer.IsValid():
        raise ValueError("The generated 3D shape is not valid according to OpenCASCADE analyzer.")

    # 写入 STEP 文件
    try:
        write_step_file(out_shape, output_step_path)
    except Exception as e:
        raise IOError(f"Failed to write STEP file. Reason: {e}")

    return True