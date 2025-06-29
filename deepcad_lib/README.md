
# pc2cad_sequence: 从点云到CAD命令序列工作流

本项目扩展了原始 [DeepCAD](https://github.com/Rundv/DeepCAD) 框架，提供了一个直接将3D点云文件 (`.ply`) 转换为CAD命令序列的端到端工作流。

此工作流引入了两个新的Python脚本：

1.  `ply_to_cad_sequence.py`: 一个端到端脚本，它接收一个 `.ply` 文件，使用预训练的PointNet++模型生成潜向量，然后通过预训练的DeepCAD解码器生成CAD命令向量，并最终保存为 `.h5` 文件。
2.  `extract_commands_from_h5.py`: 一个实用工具脚本，用于解析生成的 `.h5` 文件，并输出人类可读的CAD命令序列。这个脚本对于调试和理解模型输出至关重要，尤其是在3D可视化失败时。
3.  `inspect_h5.py`: 一个实用工具脚本，直接输出指定的 `.h5` 文件

## 功能特性

- **端到端转换**: 直接从 `.ply` 点云文件生成DeepCAD的向量格式。
- **模型集成**: 无缝加载并利用预训练的PointNet++和DeepCAD模型。
- **稳健的命令提取**: 能够查看模型的原始命令输出，绕过潜在的几何构造错误。
- **灵活的输出**: 可选择将命令序列打印到控制台，或保存为结构化的 `.txt` 文件以便分析。

## 环境设置与安装

1. **项目文件**: 确保你拥有完整的DeepCAD项目结构。将新脚本 `ply_to_cad_sequence.py` 和 `extract_commands_from_h5.py` 放置在项目的根目录下。

2. **依赖库**: 强烈建议使用Conda进行环境管理。

   * **核心库**: `PyTorch`, `NumPy`, `h5py`。

   * **点云处理**: `open3d` 是法向量估计所必需的。

     ```bash
     pip install open3d
     ```

   * **3D可视化 (可选但推荐)**: `show.py` 工具需要 `pythonocc-core`。为获得最佳兼容性，请通过conda-forge安装。

     ```bash
     conda install -c conda-forge pythonocc-core
     ```

   * **PointNet++算子**: DeepCAD的PointNet++模型依赖 `pointnet2_ops` 库。请遵循其[官方仓库](https://github.com/erikwijmans/Pointnet2_PyTorch)的指南进行安装。

3. **预训练模型**:

   *   将你预训练好的PointNet++模型 (例如, `latest.pth`) 放置在一个已知位置。
   *   确保你预训练好的DeepCAD自编码器实验 (例如, `pretrained`) 位于 `proj_log` 目录下。

## 工作流与使用方法

整个流程分为三个主要步骤。

### 步骤 1: 将点云转换为CAD向量

使用 `ply_to_cad_sequence.py` 执行端到端转换。此脚本会生成一个包含原始CAD命令向量的 `.h5` 文件。

**命令模板:**

```bash
python ply_to_cad_sequence.py \
    --ply_file /path/to/your/pointcloud.ply \
    --pc_model_path /path/to/your/pointnet_model.pth \
    --proj_dir ./proj_log \
    --ae_exp_name <your_deepcad_experiment_name> \
    --ae_ckpt <checkpoint_name> \
    --output_dir /path/to/output_directory
```

**示例:**

```bash
python ply_to_cad_sequence.py \
    --ply_file ./Labs/PlyFiles/test.ply \
    --pc_model_path ./Point++/latest.pth \
    --proj_dir ./proj_log \
    --ae_exp_name pretrained \
    --ae_ckpt 1000 \
    --output_dir ./Labs/reconstructions
```

这将在 `./Labs/reconstructions` 目录下生成一个名为 `test_reconstructed.h5` 的文件。

### 步骤 2: 可视化3D模型 (可选)

你可以尝试使用项目自带的 `utils/show.py` 脚本将生成的 `.h5` 文件可视化为3D实体。

**注意**: 如下文“理解可视化失败”部分所述，此步骤很可能会失败。

**示例:**

```bash
# 首先进入 utils 目录（必须进入该目录才能运行，否则会遇到缺少模块问题）
cd utils

# 运行脚本, 将源目录指向你的输出目录
python show.py --src ../Labs/reconstructions --form h5
```

如果弹出的窗口为空，或者你在控制台看到了 `Standard_ConstructionError` 错误，请继续执行步骤3。

### 步骤 3: 提取并检查命令序列

这是分析模型输出最可靠的方法。使用 `extract_commands_from_h5.py` 脚本可以查看模型生成的确切命令序列。

#### 打印到控制台

要快速查看单个文件的内容：

**命令:**

```bash
python extract_commands_from_h5.py --file ./Labs/reconstructions/test_reconstructed.h5
```

**预期输出:**

```
======================================================================
Processing file: test_reconstructed.h5
======================================================================
Vector Shape: (42, 17), Data Type: int32

Step  | Command    | Parameters (non-padding only)
----------------------------------------------------------------------
00:   | SOL        | []
01:   | Ext        | [192, 64, 192, 32, 128, 32, 192, 224, 128, 1, 0]
...
```

#### 保存到 `.txt` 文件

如果你想保存输出以供后续分析：
**命令:**

```bash
python extract_commands_from_h5.py --src ./Labs/reconstructions --output-mode save --output-dir ./Labs/command_logs
```

这会为源目录中的每个 `.h5` 文件创建一个对应的 `.txt` 文件，并保存在 `./Labs/command_logs` 目录下。

#### 格式化选项

默认情况下，脚本会输出纯净的Python整数。如果你需要查看原始的NumPy数据类型以便调试，可以使用 `--raw-numpy-types` 标志。

**命令:**

```bash
python extract_commands_from_h5.py --file ./Labs/reconstructions/test_reconstructed.h5 --raw-numpy-types
```

**预期输出:**

```
...
01:   | Ext        | [np.int64(192), np.int64(64), np.int64(192), ...]
...
```

## 理解可视化失败

步骤2中的可视化失败是一种非常常见的现象。典型的错误 `Standard_ConstructionError...BRepPrimAPI_MakePrism` 指向了在“拉伸”操作过程中的失败。

这**不是代码的bug**，而是CAD生成模型的一个根本性挑战。其原因是模型生成的命令序列在**几何逻辑上是无效的**。常见问题包括：

- **尝试拉伸一个空的草图。**
- **尝试拉伸一个开放的（未闭合的）线段和圆弧回路。**
- **生成了一个自相交的2D草图。**

这些问题之所以出现，是因为机器学习模型虽然擅长捕捉统计规律，但它并不内在地理解严格的、确定性的几何规则。当输入的点云与模型的训练数据分布不同时，生成的命令序列可能在语法上“看起来很像”，但在几何上却毫无意义。

## extract_commands_from_h5.py使用方式

### 打印干净的整数
```python
python extract_commands_from_h5.py --file ./reconstructions/test_reconstructed.h5
```

### 保存为txt，内容也是干净的整数
```python
python extract_commands_from_h5.py --file ./reconstructions/test_reconstructed.h5 --output-mode save
```

**预期输出/文件内容:**
```
Generated code
...
05:   | Ext        | [192, 64, 192, 32, 128, 32, 192, 32, 128, 1, 0]
...
Use code with caution.
```

### 打印带 np.int64 的原始类型
如果你需要看到原始的 NumPy 类型（例如为了调试），只需在命令行中添加 `--raw-numpy-types` 标志。
```python
python extract_commands_from_h5.py --file ./reconstructions/test_reconstructed.h5 --raw-numpy-types
```

### 保存为txt，内容也是带 np.int64 的原始类型
```python
python extract_commands_from_h5.py --file ./reconstructions/test_reconstructed.h5 --output-mode save --raw-numpy-types
```
