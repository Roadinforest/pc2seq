<template>
  <div>
    <input type="file" accept=".ply" @change="onFileChange" />
    <div ref="container" class="viewer" />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as THREE from 'three'
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js'

const container = ref(null)
let renderer, scene, camera, controls, animationId
let pointCloud

// 初始化 Three.js 场景
function initScene() {
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x000000)

  camera = new THREE.PerspectiveCamera(75, container.value.clientWidth / container.value.clientHeight, 0.1, 1000)
  camera.position.set(0, 0, 5)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(container.value.clientWidth, container.value.clientHeight)
  container.value.appendChild(renderer.domElement)

  // 添加简单光源
  const ambientLight = new THREE.AmbientLight(0xffffff, 1)
  scene.add(ambientLight)

  // 轨道控制（可选）
  import('three/examples/jsm/controls/OrbitControls.js').then(({ OrbitControls }) => {
    controls = new OrbitControls(camera, renderer.domElement)
    controls.update()
  })
}

// 渲染函数
function animate() {
  animationId = requestAnimationFrame(animate)
  controls && controls.update()
  renderer.render(scene, camera)
}

// 加载并显示 PLY 点云
function loadPLY(buffer) {
  const loader = new PLYLoader()
  const geometry = loader.parse(buffer)

  geometry.computeVertexNormals()

  const material = new THREE.PointsMaterial({
    size: 0.01,
    vertexColors: geometry.hasAttribute('color')
  })

  if (pointCloud) {
    scene.remove(pointCloud)
  }

  pointCloud = new THREE.Points(geometry, material)
  scene.add(pointCloud)

  // 根据点云大小调整相机
  geometry.computeBoundingSphere()
  const center = geometry.boundingSphere.center
  camera.position.set(center.x, center.y, center.z + geometry.boundingSphere.radius * 3)
  camera.lookAt(center)
}

function onFileChange(event) {
  const file = event.target.files[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = e => {
    const arrayBuffer = e.target.result
    loadPLY(arrayBuffer)
  }
  reader.readAsArrayBuffer(file)
}

onMounted(() => {
  initScene()
  animate()
})

onBeforeUnmount(() => {
  animationId && cancelAnimationFrame(animationId)
  renderer && renderer.dispose()
  controls && controls.dispose()
})
</script>

<style scoped>
.viewer {
  width: 100%;
  height: 600px;
  background-color: #000;
}
</style>
