<template>
  <div class="step-viewer-wrapper">
    <div v-if="start">Waiting for the 3D Model ...</div>
    <div v-if="loading" class="loading-overlay">Loading 3D Model...</div>
    <div v-if="error" class="error-overlay">{{ error }}</div>
    <canvas ref="threeCanvas" class="viewer-canvas"></canvas>
  </div>


</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import occtimportjs from 'occt-import-js'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

const props = defineProps({
  fileUrl: { type: String, required: true }
})

const start = ref(true)
const loading = ref(false)
const error = ref(null)
const result = ref(null)
const threeCanvas = ref(null)
let scene, camera, renderer, controls, modelGroup, animationId

watch(() => props.fileUrl, (newUrl) => {
  if (newUrl) {
    processUrl(newUrl)
  }
})

onMounted(() => {
  nextTick(() => {
    initThreeDScene()
    if (props.fileUrl) {
      processUrl(props.fileUrl)
    }
  })
  window.addEventListener('resize', onWindowResize)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  renderer?.dispose()
  controls?.dispose()
  clearModel()
  scene = camera = renderer = controls = modelGroup = null
  window.removeEventListener('resize', onWindowResize)
})

async function processUrl(url) {
  start.value = false
  loading.value = true
  error.value = null
  result.value = null
  clearModel()

  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const buffer = await res.arrayBuffer()
    const content = new Uint8Array(buffer)

    const occt = await occtimportjs({
      locateFile: (path, prefix) => path.endsWith('.wasm') ? `/${path}` : prefix + path
    })

    const lower = url.toLowerCase()
    const params = {
      linearUnit: 'millimeter',
      linearDeflectionType: 'bounding_box_ratio',
      linearDeflection: 0.1,
      angularDeflection: 0.5
    }

    let importResult
    if (lower.endsWith('.step') || lower.endsWith('.stp')) {
      importResult = occt.ReadStepFile(content, params)
    } else if (lower.endsWith('.iges') || lower.endsWith('.igs')) {
      importResult = occt.ReadIgesFile(content, params)
    } else if (lower.endsWith('.brep')) {
      importResult = occt.ReadBrepFile(content, params)
    } else {
      throw new Error('Unsupported file type')
    }

    result.value = importResult
    if (!importResult.success) throw new Error(importResult.error || 'Import failed')

    await nextTick()
    renderModel(importResult)
  } catch (e) {
    error.value = e.message
    console.error(e)
  } finally {
    loading.value = false
  }
}

function initThreeDScene() {
  const canvas = threeCanvas.value
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf0f0f0)

  camera = new THREE.PerspectiveCamera(75, canvas.clientWidth / canvas.clientHeight, 0.1, 1000)
  camera.position.set(5, 5, 5)

  renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.setSize(canvas.clientWidth, canvas.clientHeight)

  const ambient = new THREE.AmbientLight(0xffffff, 0.5)
  const dir = new THREE.DirectionalLight(0xffffff, 0.8)
  dir.position.set(1, 1, 1).normalize()
  scene.add(ambient, dir)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true

  modelGroup = new THREE.Group()
  scene.add(modelGroup)

  animate()
}

function animate() {
  animationId = requestAnimationFrame(animate)
  controls.update()
  renderer.render(scene, camera)
}

function clearModel() {
  if (modelGroup) {
    while (modelGroup.children.length) {
      const obj = modelGroup.children[0]
      modelGroup.remove(obj)
      obj.geometry?.dispose()
      if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose())
      else obj.material?.dispose()
    }
  }
}

function renderModel(importResult) {
  clearModel()
  if (!importResult.meshes) return

  const bbox = new THREE.Box3()
  const center = new THREE.Vector3()

  importResult.meshes.forEach(mesh => {
    if (!mesh.attributes?.position?.array || !mesh.index?.array) return

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(mesh.attributes.position.array), 3))

    if (mesh.attributes.normal?.array) {
      geometry.setAttribute('normal', new THREE.BufferAttribute(new Float32Array(mesh.attributes.normal.array), 3))
    } else {
      geometry.computeVertexNormals()
    }

    geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(mesh.index.array), 1))

    const color = mesh.color?.length === 3
      ? new THREE.Color(...mesh.color.map(c => c / 255))
      : new THREE.Color(0xcccccc)

    const material = new THREE.MeshStandardMaterial({ color, side: THREE.DoubleSide })
    const threeMesh = new THREE.Mesh(geometry, material)
    modelGroup.add(threeMesh)
    bbox.expandByObject(threeMesh)
  })

  if (!bbox.isEmpty()) {
    bbox.getCenter(center)
    const size = bbox.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z)
    const fov = camera.fov * (Math.PI / 180)
    let cameraZ = maxDim / (2 * Math.tan(fov / 2))
    cameraZ *= (camera.aspect > 1 ? camera.aspect : 1)

    camera.position.copy(center)
    camera.position.z += cameraZ
    camera.position.y += cameraZ * 0.5
    camera.lookAt(center)

    controls.target.copy(center)
    controls.update()
  }
}

function onWindowResize() {
  const canvas = threeCanvas.value
  const parent = canvas.parentElement
  const width = parent.clientWidth
  const height = Math.min(width * 0.75, 500)

  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}
</script>

<style scoped>
.step-viewer-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.viewer-canvas {
  width: 100%;
  height: 100%;
}

.loading-overlay,
.error-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(0, 0, 0, 0.5);
  color: white;
  font-size: 1.2em;
}

.error-overlay {
  background-color: rgba(217, 83, 79, 0.7);
}
</style>
