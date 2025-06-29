import h5py
import numpy as np
import argparse  # Import the argparse module
from cadlib.macro import ALL_COMMANDS  # 确保 cadlib 在路径中

def main():
    parser = argparse.ArgumentParser(description="Read and display CAD command data from an H5 file.")
    parser.add_argument("--h5_path", type=str, required=True,
                        help="Path to the H5 file containing 'out_vec' data.")
    args = parser.parse_args()

    H5_PATH = args.h5_path

    try:
        with h5py.File(H5_PATH, 'r') as f:
            if 'out_vec' in f:
                vec = f['out_vec'][:]
                print(f"File: {H5_PATH}")
                print(f"Vector shape: {vec.shape}")
                print(f"Data type: {vec.dtype}")
                print("-" * 30)

                # 打印前20条命令
                print("First 20 commands:")
                for i, row in enumerate(vec[:20]):
                    cmd_idx = int(row[0])
                    cmd_name = ALL_COMMANDS[cmd_idx] if cmd_idx < len(ALL_COMMANDS) else f"INVALID({cmd_idx})"
                    args = row[1:]
                    print(f"{i:02d}: {cmd_name:<10} | Args: {args}")

            else:
                print(f"'out_vec' not found in {H5_PATH}")
    except FileNotFoundError:
        print(f"Error: The file '{H5_PATH}' was not found. Please check the path.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()


# python inspect_h5_data.py --h5_path ./your/other/file.h5