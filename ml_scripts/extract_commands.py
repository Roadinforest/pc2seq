# backend/ml_scripts/extract_commands.py

import numpy as np
import os
import sys

# --- 关键：确保能导入 deepcad_lib 中的模块 ---
# 这个脚本被 run_inference.py 调用，所以我们需要确保路径正确
# run_inference.py 已经处理了 sys.path, 但为了独立测试，这里也可以加上
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(SCRIPT_DIR, '..', 'deepcad_lib')))

try:
    from cadlib.macro import ALL_COMMANDS, N_ARGS, EOS_IDX
except ImportError:
    # 提供一个备用方案，以防 cadlib 无法导入，虽然在正常流程中不应该发生
    print("Warning: Could not import from cadlib.macro. Using fallback values.")
    ALL_COMMANDS = ['Line', 'Arc', 'Circle', 'EOS', 'SOS', 'SOL', 'EOL', 'Ext']
    N_ARGS = 16
    EOS_IDX = 3  # 假设值


def get_command_sequence_string(vec):
    """
    将模型输出的向量 (vec) 转换为一个格式化的、人类可读的字符串。

    Args:
        vec (np.array): The CAD vector from the model, shape (L, 1 + N_ARGS).

    Returns:
        str: A multi-line string representing the command sequence.
    """
    lines = []

    if not isinstance(vec, np.ndarray) or vec.ndim != 2 or vec.shape[1] != (1 + N_ARGS):
        error_msg = f"Error: Input vector has an invalid shape or type. Expected a NumPy array of shape (L, {1 + N_ARGS}), but got {type(vec)} with shape {getattr(vec, 'shape', 'N/A')}"
        lines.append(error_msg)
        return "\n".join(lines)

    lines.append(f"Generated Command Sequence (Vector Shape: {vec.shape})")
    lines.append("-" * 70)
    lines.append(f"{'Step':<5} | {'Command':<10} | {'Parameters'}")
    lines.append("-" * 70)

    for i, row in enumerate(vec):
        cmd_idx = int(row[0])

        try:
            cmd_name = ALL_COMMANDS[cmd_idx]
        except IndexError:
            cmd_name = f"INVALID({cmd_idx})"

        # 将参数转换为原生 Python int 类型以获得干净的输出
        args = row[1:].astype(np.int64)
        meaningful_args = [int(arg) for arg in args if arg != -1]

        lines.append(f"{i:02d}:   | {cmd_name:<10} | {meaningful_args}")

        # 如果遇到序列结束符，就停止处理
        if cmd_idx == EOS_IDX:
            lines.append("-" * 70)
            lines.append("End of Sequence token found.")
            break

    return "\n".join(lines)