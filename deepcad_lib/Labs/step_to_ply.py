import sys
import open3d as o3d
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Extend.DataExchange import read_step_file
from OCC.Extend.TopologyUtils import TopologyExplorer
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRep import BRep_Tool_Triangulation
from OCC.Core.TopLoc import TopLoc_Location
import numpy as np

# 将step文件转换为点云
def step_to_mesh(step_file):
    shape = read_step_file(step_file)
    
    # 将STEP文件的shape三角化
    mesh = BRepMesh_IncrementalMesh(shape, 0.1)
    mesh.Perform()

    vertices = []
    for face in TopologyExplorer(shape).faces():
        triangulation = BRep_Tool_Triangulation(face, TopLoc_Location())
        if triangulation is None:
            continue
        for i in range(1, triangulation.NbNodes() + 1):
            pt = triangulation.Node(i)
            vertices.append([pt.X(), pt.Y(), pt.Z()])

    return np.array(vertices)

def convert_step_to_ply(step_path, ply_path, sample_points=2048):
    print(f"Reading STEP file: {step_path}")
    points = step_to_mesh(step_path)
    if points.shape[0] == 0:
        print("No points found in STEP file.")
        return

    print(f"Loaded {points.shape[0]} raw vertices from STEP mesh.")

    # 创建 Open3D 点云对象
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    # 可选：进行均匀或泊松采样
    if sample_points and points.shape[0] > sample_points:
        pcd = pcd.random_down_sample(sample_points / points.shape[0])

    # 保存为 .ply
    o3d.io.write_point_cloud(ply_path, pcd)
    print(f"Saved point cloud to: {ply_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python step_to_ply.py input.step output.ply")
        sys.exit(1)

    step_path = sys.argv[1]
    ply_path = sys.argv[2]
    convert_step_to_ply(step_path, ply_path)

