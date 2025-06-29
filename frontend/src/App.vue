<template>
  <div class="app-container">
    <header>
      <h1>Point Cloud to CAD Sequence</h1>
      <p>Upload a .ply file, view it in 3D, and generate its CAD command sequence using AI.</p>
    </header>

    <main>
      <div class="controls">
        <label for="file-upload" class="custom-file-upload" :class="{ disabled: isProcessing }">
          <span class="icon"></span> {{ file ? file.name : '1. Select a .PLY File' }}
        </label>
        <input id="file-upload" type="file" accept=".ply" @change="onFileChange" :disabled="isProcessing" />
        <button @click="processOnServer" :disabled="!file || isProcessing">
          <span v-if="isProcessing" class="spinner"></span>
          {{ isProcessing ? 'Processing...' : '2. Generate Sequence' }}
        </button>
      </div>

      <div class="content-wrapper">
        <div class="viewer-container">
          <h3>3D Point Cloud Viewer</h3>
          <div ref="container" class="viewer">
            <p v-if="!file" class="viewer-placeholder">Select a file to view the point cloud</p>
          </div>
        </div>

        <div class="results-container">
          <h3>Inference Progress & Results</h3>
          <div class="progress-box">
            <p v-if="progressUpdates.length === 0" class="placeholder">
              Progress will be shown here...
            </p>
            <ul>
              <li v-for="(update, index) in progressUpdates" :key="index" :class="['update-item', update.type]">
                <span class="timestamp">{{ update.timestamp }}</span>
                {{ update.data }}
              </li>
            </ul>
          </div>
          <div class="sequence-box">
            <pre v-if="finalSequence">{{ finalSequence }}</pre>
            <p v-if="!finalSequence" class="placeholder">
              Generated CAD sequence will appear here...
            </p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import * as THREE from 'three';
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const container = ref(null);
let renderer, scene, camera, controls, animationId;
let pointCloud;

const file = ref(null);
const fileId = ref(null);
const isProcessing = ref(false);
const progressUpdates = ref([]);
const finalSequence = ref('');

const API_BASE_URL = 'http://localhost:8000/api';

function onFileChange(event) {
  const selectedFile = event.target.files[0];
  if (!selectedFile) return;

  const viewerPlaceholder = document.querySelector('.viewer-placeholder');
  if (viewerPlaceholder) viewerPlaceholder.style.display = 'none';

  file.value = selectedFile;
  finalSequence.value = '';
  progressUpdates.value = [];
  fileId.value = null;

  const reader = new FileReader();
  reader.onload = e => loadPLY(e.target.result);
  reader.readAsArrayBuffer(selectedFile);
}

// --- Server Interaction Logic ---
async function uploadFile() {
  if (!file.value) return null;
  const formData = new FormData();
  formData.append('file', file.value);
  try {
    const response = await fetch(`${API_BASE_URL}/upload/`, { method: 'POST', body: formData });
    if (!response.ok) throw new Error(`Server responded with ${response.status}`);
    const data = await response.json();
    return data.file_id;
  } catch (error) {
    addProgressUpdate('error', `Upload Error: ${error.message}`);
    return null;
  }
}

function addProgressUpdate(type, data) {
  const timestamp = new Date().toLocaleTimeString();
  progressUpdates.value.push({ type, data, timestamp });
}

async function processOnServer() {
  isProcessing.value = true;
  progressUpdates.value = [];
  finalSequence.value = '';

  addProgressUpdate('status', 'Uploading file to server...');
  const uploadedFileId = await uploadFile();

  if (!uploadedFileId) {
    isProcessing.value = false;
    return;
  }
  fileId.value = uploadedFileId;

  addProgressUpdate('status', 'File uploaded. Starting inference...');

  const eventSource = new EventSource(`${API_BASE_URL}/process-ply/?file_id=${fileId.value}`);

  eventSource.onmessage = (event) => {
    const message = JSON.parse(event.data);
    addProgressUpdate(message.type, message.data);

    if (message.type === 'result') {
      finalSequence.value = message.data;
      eventSource.close();
      isProcessing.value = false;
    } else if (message.type === 'error') {
      eventSource.close();
      isProcessing.value = false;
    }
  };

  eventSource.onerror = () => {
    addProgressUpdate('error', 'Connection to server failed. Is the Django server running?');
    eventSource.close();
    isProcessing.value = false;
  };
}


// 为简洁起见，将未变动的 Three.js 代码折叠
onMounted(() => {
  initScene();
  animate();
});

onBeforeUnmount(() => {
  if (animationId) cancelAnimationFrame(animationId);
  if (renderer) renderer.dispose();
  if (controls) controls.dispose();
});
function initScene() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a1a);
  const containerEl = container.value;
  if (!containerEl) return;
  camera = new THREE.PerspectiveCamera(75, containerEl.clientWidth / containerEl.clientHeight, 0.1, 1000);
  camera.position.set(0, 0, 5);
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(containerEl.clientWidth, containerEl.clientHeight);
  containerEl.appendChild(renderer.domElement);
  const ambientLight = new THREE.AmbientLight(0xffffff, 1.5);
  scene.add(ambientLight);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  window.addEventListener('resize', onWindowResize);
}
function animate() {
  animationId = requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
function onWindowResize() {
  const containerEl = container.value;
  if (!containerEl) return;
  camera.aspect = containerEl.clientWidth / containerEl.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(containerEl.clientWidth, containerEl.clientHeight);
}
function loadPLY(buffer) {
  const loader = new PLYLoader();
  const geometry = loader.parse(buffer);
  geometry.computeVertexNormals();
  const material = new THREE.PointsMaterial({ size: 0.015, vertexColors: geometry.hasAttribute('color') });
  if (pointCloud) scene.remove(pointCloud);
  pointCloud = new THREE.Points(geometry, material);
  scene.add(pointCloud);
  geometry.computeBoundingSphere();
  const sphere = geometry.boundingSphere;
  controls.target.copy(sphere.center);
  camera.position.copy(sphere.center).add(new THREE.Vector3(0, 0, sphere.radius * 2.5));
  camera.lookAt(sphere.center);
  controls.update();
}

</script>

<style>
/* 包含上次提供的所有CSS样式，并增加了一些美化 */
:root {
  --primary-color: #42b883;
  --secondary-color: #35495e;
  --bg-color: #f0f2f5;
  --widget-bg: #ffffff;
  --text-color: #333;
  --border-color: #ddd;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  background-color: var(--bg-color);
  margin: 0;
  color: var(--text-color);
}

.app-container {
  max-width: 1600px;
  margin: 0 auto;
  padding: 2rem;
}

header {
  text-align: center;
  margin-bottom: 2rem;
}

header h1 {
  color: var(--secondary-color);
}

main {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.controls {
  display: flex;
  gap: 1rem;
  align-items: center;
  background: var(--widget-bg);
  padding: 1rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

input[type="file"] {
  display: none;
}

.custom-file-upload {
  border: 2px dashed var(--border-color);
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 10px 15px;
  cursor: pointer;
  background-color: #f9f9f9;
  border-radius: 5px;
  transition: all 0.2s ease-in-out;
}

.custom-file-upload:hover {
  border-color: var(--primary-color);
  background-color: #e9f5ee;
}

.custom-file-upload.disabled {
  background-color: #e9ecef;
  cursor: not-allowed;
  border-style: solid;
}

button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  padding: 12px 22px;
  border-radius: 5px;
  cursor: pointer;
  font-size: 16px;
  font-weight: 500;
  transition: all 0.2s ease-in-out;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

button:hover:not(:disabled) {
  background-color: #36a474;
  transform: translateY(-2px);
}

button:disabled {
  background-color: #95a5a6;
  cursor: not-allowed;
}

.content-wrapper {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
  gap: 2rem;
}

.viewer-container,
.results-container {
  background: var(--widget-bg);
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.viewer {
  width: 100%;
  height: 550px;
  background-color: #000;
  border-radius: 5px;
  position: relative;
}

.progress-box {
  height: 250px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  padding: 10px;
  border-radius: 5px;
  margin-bottom: 1rem;
  background-color: #fdfdfd;
}

.progress-box ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.update-item {
  padding: 8px 5px;
  border-bottom: 1px solid #eee;
  display: flex;
  gap: 1rem;
  align-items: center;
}

.update-item.status {
  color: #555;
}

.update-item.error {
  color: #e74c3c;
  font-weight: bold;
}

.timestamp {
  font-size: 0.8em;
  background-color: #eee;
  padding: 2px 6px;
  border-radius: 3px;
  color: #777;
}

.sequence-box {
  height: 300px;
  overflow-y: auto;
  border: 1px solid var(--border-color);
  padding: 0;
  border-radius: 5px;
}

pre {
  background-color: #f4f6f8;
  margin: 0;
  padding: 15px;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
  font-size: 0.9em;
  line-height: 1.6;
}

.placeholder,
.viewer-placeholder {
  color: #aaa;
  text-align: center;
  padding: 40px 20px;
  font-style: italic;
}

.viewer-placeholder {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #666;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #fff;
  animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>