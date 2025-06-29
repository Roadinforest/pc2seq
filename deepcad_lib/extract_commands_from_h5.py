import h5py
import numpy as np
import argparse
import os
import glob
from cadlib.macro import ALL_COMMANDS, N_ARGS


def get_command_sequence_string(vec, raw_numpy_types=False):
    """
    将向量转换为格式化的命令序列字符串。

    Args:
        vec (np.array): The CAD vector.
        raw_numpy_types (bool): 如果为True，参数将以np.int64()格式显示。
                                如果为False，参数将被转换为原生Python int。
    """
    lines = []

    if vec.ndim != 2 or vec.shape[1] != (1 + N_ARGS):
        lines.append(f"Error: Vector shape is invalid. Expected (L, {1 + N_ARGS}), but got {vec.shape}")
        return "\n".join(lines)

    lines.append(f"Vector Shape: {vec.shape}, Data Type: {vec.dtype}\n")
    lines.append(f"{'Step':<5} | {'Command':<10} | {'Parameters (non-padding only)'}")
    lines.append("-" * 70)

    for i, row in enumerate(vec):
        cmd_idx = int(row[0])

        try:
            cmd_name = ALL_COMMANDS[cmd_idx]
        except IndexError:
            cmd_name = f"INVALID({cmd_idx})"

        args_np = row[1:].astype(np.int64)  # 统一使用int64处理

        # 过滤掉填充值
        meaningful_args_np = [arg for arg in args_np if arg != -1]

        # 根据选项决定最终的参数列表格式
        if raw_numpy_types:
            final_args = meaningful_args_np
        else:
            final_args = [int(arg) for arg in meaningful_args_np]  # 转换为原生int

        lines.append(f"{i:02d}:   | {cmd_name:<10} | {final_args}")

        if cmd_name == 'EOS':
            lines.append("-" * 70)
            lines.append("End of Sequence token found.")
            break

    return "\n".join(lines)


def process_h5_file(h5_path, output_mode, output_dir=None, raw_numpy_types=False):
    """
    读取单个H5文件，并根据输出模式处理命令序列。
    """
    if not os.path.exists(h5_path):
        print(f"Error: File not found at {h5_path}")
        return

    file_basename = os.path.basename(h5_path)

    try:
        with h5py.File(h5_path, 'r') as f:
            if 'out_vec' not in f:
                print(f"[{file_basename}] Error: 'out_vec' dataset not found.")
                return

            vec = f['out_vec'][:]

        # 生成命令序列字符串，传入新的格式化选项
        sequence_str = get_command_sequence_string(vec, raw_numpy_types)

        # 根据模式选择输出方式
        if output_mode == 'print':
            header = "=" * 70 + f"\nProcessing file: {file_basename}\n" + "=" * 70
            print(header)
            print(sequence_str)
            print("\n")
        elif output_mode == 'save':
            if output_dir is None:
                output_dir = os.path.dirname(h5_path)
            os.makedirs(output_dir, exist_ok=True)

            txt_filename = os.path.splitext(file_basename)[0] + '.txt'
            output_path = os.path.join(output_dir, txt_filename)

            try:
                with open(output_path, 'w') as txt_file:
                    txt_file.write(sequence_str)
                print(f"Successfully saved command sequence from '{file_basename}' to '{output_path}'")
            except IOError as e:
                print(f"Error writing to file '{output_path}': {e}")

    except Exception as e:
        print(f"An error occurred while processing '{file_basename}': {e}")


def main(args):
    if args.file:
        process_h5_file(args.file, args.output_mode, args.output_dir, args.raw_numpy_types)
    elif args.src:
        if not os.path.isdir(args.src):
            print(f"Error: Source directory not found at {args.src}")
            return

        h5_files = sorted(glob.glob(os.path.join(args.src, "*.h5")))

        if not h5_files:
            print(f"No .h5 files found in directory: {args.src}")
            return

        print(f"Found {len(h5_files)} H5 files to process.\n")

        for h5_path in h5_files:
            process_h5_file(h5_path, args.output_mode, args.output_dir, args.raw_numpy_types)
    else:
        print("Please provide a source directory with --src or a single file with --file.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Extract human-readable CAD command sequences from .h5 files.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--src', type=str, help="Source directory containing the .h5 files.")
    input_group.add_argument('--file', type=str, help="Path to a single .h5 file.")

    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--output-mode',
        type=str,
        choices=['print', 'save'],
        default='print',
        help="Choose the output mode:\n 'print': Print to console (default).\n 'save': Save to .txt files."
    )
    output_group.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help="Directory to save the output .txt files (used with --output-mode=save).\n"
             "If not given, saves files alongside their .h5 counterparts."
    )

    format_group = parser.add_argument_group('Formatting Options')
    format_group.add_argument(
        '--raw-numpy-types',
        action='store_true',
        help="If set, display parameters with raw NumPy types (e.g., np.int64(192)).\n"
             "Otherwise, they are converted to clean Python integers (default)."
    )

    args = parser.parse_args()
    main(args)