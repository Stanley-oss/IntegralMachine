<template>
  <div :class="['integral-machine-container', theme]">
    <header class="app-header">
      <h1 class="title">Integral Machine</h1>
      <button @click="toggleTheme" class="dark-mode-toggle">
        {{ theme === 'light' ? '🌙' : '☀️' }}
      </button>
    </header>

    <main class="app-main">
      <div class="card canvas-card">
        <div class="card-header">
          <span>Handwriting Recognition</span>
          <button @click="clearAll" class="toolbar-btn">Clear</button>
        </div>
        <canvas
          ref="canvasRef"
          @mousedown="startDrawing"
          @mousemove="draw"
          @mouseup="endDrawing"
          @mouseleave="endDrawing"
          class="handwriting-canvas"
        ></canvas>
        <canvas ref="hiddenCanvasRef" class="hidden-canvas"></canvas>
        <div v-if="isLoading.recognition" class="canvas-overlay">
          Recognizing...
        </div>
      </div>

      <div class="card formula-input-card">
        <div ref="formulaDisplayRef" class="formula-display"></div>
        <button
          @click="calculateIntegral"
          class="go-button"
          :disabled="!latexFormula || isLoading.calculation"
        >
          <span v-if="!isLoading.calculation">Go</span>
          <span v-else class="loader"></span>
        </button>
      </div>

      <section v-if="hasSolution" class="results-section">
        <div class="card solution-card solution-header">
          <h3>Solution</h3>
          <div ref="resultDisplayRef" class="display-math"></div>
        </div>
        <div class="card steps-card solution-steps">
          <h4>Solution Steps</h4>
          <div class="steps-list">
            <div
              v-for="(step, idx) in calculationResult.steps"
              :key="idx"
              class="step-item"
            >
              <div class="step-rule">{{ step.rule }}</div>
              <div class="step-formula" :ref="el => stepRefs[idx] = el"></div>
            </div>
          </div>
        </div>
      </section>

      <div v-if="apiError" class="error-message">
        <p><strong>Error:</strong> {{ apiError }}</p>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import katex from 'katex';
import 'katex/dist/katex.min.css';

const theme = ref('light');
const isLoading = ref({ recognition: false, calculation: false });
const canvasRef = ref(null);
const hiddenCanvasRef = ref(null);
let ctx, hiddenCtx;
let drawing = false;

const latexFormula = ref('');
const calculationResult = ref({ answer: '', steps: [] });
const apiError = ref('');

const formulaDisplayRef = ref(null);
const resultDisplayRef = ref(null);
const stepRefs = ref([]);

const hasSolution = computed(
  () => !!calculationResult.value.answer || calculationResult.value.steps.length > 0
);

onMounted(() => {
  const c = canvasRef.value;
  const hc = hiddenCanvasRef.value;

  const parentComputedStyle = getComputedStyle(c.parentElement);
  const parentPaddingLeft = parseFloat(parentComputedStyle.paddingLeft);
  const parentPaddingRight = parseFloat(parentComputedStyle.paddingRight);

  const parentRect = c.parentElement.getBoundingClientRect();
  const width = parentRect.width - parentPaddingLeft - parentPaddingRight;
  const height = 380;
  const dpr = window.devicePixelRatio || 1;

  [c, hc].forEach(canvas => {
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
  });

  [c, hc].forEach(canvas => {
    canvas.width = width * dpr;
    canvas.height = height * dpr;
  });

  ctx = c.getContext('2d');
  hiddenCtx = hc.getContext('2d');
  ctx.scale(dpr, dpr);
  hiddenCtx.scale(dpr, dpr);

  initCanvas();
});

function initCanvas() {
  ctx.fillStyle = theme.value === 'light' ? '#fff' : '#2d2d2d';
  ctx.fillRect(0, 0, canvasRef.value.width, canvasRef.value.height);
  
  ctx.strokeStyle = theme.value === 'light' ? '#000' : '#fff';
  ctx.lineWidth = 3;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  hiddenCtx.fillStyle = '#fff';
  hiddenCtx.fillRect(0, 0, hiddenCanvasRef.value.width, hiddenCanvasRef.value.height);
  hiddenCtx.strokeStyle = '#000';
  hiddenCtx.lineWidth = 3;
  hiddenCtx.lineCap = 'round';
  hiddenCtx.lineJoin = 'round';
}

watch(theme, () => {
  clearAll();
  initCanvas();
});

function getPos(e) {
  const rect = canvasRef.value.getBoundingClientRect();
  return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}
function startDrawing(e) {
  drawing = true;
  const { x, y } = getPos(e);
  ctx.beginPath(); ctx.moveTo(x, y);
  hiddenCtx.beginPath(); hiddenCtx.moveTo(x, y);
}
function draw(e) {
  if (!drawing) return;
  const { x, y } = getPos(e);
  ctx.lineTo(x, y); ctx.stroke();
  hiddenCtx.lineTo(x, y); hiddenCtx.stroke();
}
function endDrawing() {
  if (!drawing) return;
  drawing = false;
  ctx.closePath(); hiddenCtx.closePath();
  const base64 = hiddenCanvasRef.value.toDataURL('image/png').split(',')[1];
  recognizeHandwriting(base64);
}

function clearAll() {
  ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height);
  hiddenCtx.clearRect(0, 0, hiddenCanvasRef.value.width, hiddenCanvasRef.value.height);
  initCanvas();
  latexFormula.value = '';
  calculationResult.value = { answer: '', steps: [] };
  apiError.value = '';
  formulaDisplayRef.value && (formulaDisplayRef.value.innerHTML = '');
  resultDisplayRef.value && (resultDisplayRef.value.innerHTML = '');
}

async function recognizeHandwriting(imageData) {
  isLoading.value.recognition = true;
  apiError.value = '';
  try {
    const res = await fetch('http://localhost:8000/api/handwriting', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: imageData }),
    });
    const { latex } = await res.json();
    latexFormula.value = latex;
  } catch {
    apiError.value = 'Recognition failed, please try again';
  } finally {
    isLoading.value.recognition = false;
  }
}

async function calculateIntegral() {
  if (!latexFormula.value) return;
  isLoading.value.calculation = true;
  apiError.value = '';
  calculationResult.value = { answer: '', steps: [] };
  try {
    const res = await fetch('http://localhost:8000/api/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ formula: latexFormula.value }),
    });
    const data = await res.json();
    calculationResult.value = data;
  } catch {
    apiError.value = 'Calculation failed, please try again';
  } finally {
    isLoading.value.calculation = false;
  }
}

function toggleTheme() {
  clearAll();
  theme.value = theme.value === 'light' ? 'dark' : 'light';
}

function renderKatex(el, expr) {
  if (!el) return;
  try {
    katex.render(expr, el, { displayMode: true, throwOnError: false });
  } catch {
    el.textContent = expr;
  }
}

watch(latexFormula, async val => {
  await nextTick();
  renderKatex(formulaDisplayRef.value, val);
});
watch(() => calculationResult.value.answer, async val => {
  await nextTick();
  renderKatex(resultDisplayRef.value, val);
});
watch(() => calculationResult.value.steps, async steps => {
  stepRefs.value = [];
  await nextTick();
  calculationResult.value.steps.forEach((step, i) => {
    const expr = `${step.before} \\Rightarrow ${step.after}`;
    renderKatex(stepRefs.value[i], expr);
  });
}, { deep: true });
</script>

<style scoped>
:global(html, body) {
  margin: 0;
  padding: 0;
  overflow: hidden;
  height: 100%;
  background: inherit;
}

:global(html) {
  background: var(--bg-color);
}
:global(*), :global(*::before), :global(*::after) {
  box-sizing: border-box;
}

.integral-machine-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-color);
  color: var(--text-color);
  transition: background 0.3s, color 0.3s;
  overflow: hidden;
}

.integral-machine-container.light {
  --bg-color: #f8f9fa;
  --text-color: #333;
  --card-bg: #fff;
  --border: #ddd;
  --primary: #e74c3c;
  --primary-light: #c0392b;
}
.integral-machine-container.dark {
  --bg-color: #1a1a1a;
  --text-color: #fff;
  --card-bg: #2d2d2d;
  --border: #555;
  --primary: #ff6b6b;
  --primary-light: #e74c3c;
}

.app-header {
  display: flex;
  align-items: center;
  padding: 20px 5vw;
  max-width: 100vw;
  margin: 0 auto;
}

.title {
  flex-grow: 1;
  text-align: center;
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--primary);
  margin: 0;
}

.dark-mode-toggle {
  background: none;
  border: 2px solid var(--border);
  border-radius: 50%;
  width: 50px;
  height: 50px;
  font-size: 1.5rem;
  cursor: pointer;
  transition: transform 0.3s;
}
.dark-mode-toggle:hover {
  transform: scale(1.1);
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 0;
  padding-bottom: 40px;
  width: 100%;
  max-width: 100%;
  overflow-y: auto;
  height: calc(100vh - 140px);
}

.card {
  background: var(--card-bg);
  border: 2px solid var(--border);
  border-radius: 15px;
  padding: 20px;
  margin-bottom: 20px;
  width: 90%;
  max-width: 900px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  transition: background 0.3s, box-shadow 0.3s;
}

.canvas-card {
  position: relative;
}

.canvas-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.toolbar-btn {
  background: transparent;
  border: 2px solid var(--border);
  border-radius: 8px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.3s;
  color: var(--text-color);
}
.toolbar-btn:hover {
  background: var(--border);
}

.hidden-canvas { display: none; }

.handwriting-canvas {
  display: block;
  border: 2px solid var(--border);
  border-radius: 15px;
  background: var(--card-bg);
  cursor: crosshair;
  width: 100%;
}

.canvas-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0,0,0,0.5);
  color: #fff;
  font-size: 1.2rem;
  border-radius: 15px;
}

.formula-input-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  height: 180px;
  gap: 40px;
}

.formula-display {
  flex: 1;
  background: var(--card-bg);
  border: 2px solid var(--border);
  border-radius: 10px;
  padding: 15px;
  font-size: 1.5rem;
  height: 120px;
  overflow-x: auto;
  overflow-y: auto;
  word-wrap: break-word;
  overflow-wrap: break-word;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.go-button {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 20px 30px;
  font-size: 1.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.3s, transform 0.3s, box-shadow 0.3s;
  min-width: 120px;
  height: 120px;
  flex-shrink: 0;
}
.go-button:hover:not(:disabled) {
  background: var(--primary-light);
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(231,76,60,0.3);
}
.go-button:disabled {
  background: #bdc3c7;
  cursor: not-allowed;
  transform: none;
}

.results-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  width: 90%;
  max-width: 900px;
}

.solution-header h3,
.solution-steps h4 {
  margin: 0 0 20px;
  color: var(--text-color);
}

.display-math,
.step-formula {
  width: 100%;
  font-size: 1.5rem;
}

.steps-list {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 10px;
}

.step-item {
  padding: 20px;
  border-left: 4px solid var(--primary);
  border-radius: 10px;
  background: var(--card-bg);
  transition: transform 0.3s, box-shadow 0.3s;
  margin-bottom: 15px;
}
.step-item:hover {
  transform: translateX(5px);
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.step-rule {
  font-weight: 600;
  margin-bottom: 10px;
}

.error-message {
  background: #e74c3c;
  color: #fff;
  padding: 15px;
  border-radius: 10px;
  text-align: center;
  font-weight: 600;
  width: 90%;
  max-width: 900px;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .card,
  .error-message,
  .results-section {
    width: 95%;
  }
  .title {
    font-size: 2rem;
  }
  .app-header {
    padding: 20px 20px;
  }
  .formula-input-card {
    flex-direction: column;
    align-items: stretch;
    gap: 15px;
    height: auto;
  }
  .formula-display {
    height: 80px;
  }
  .go-button {
    width: 100%;
    height: 80px;
  }
}

@media (max-width: 480px) {
  .title {
    font-size: 1.8rem;
  }
  .dark-mode-toggle {
    width: 40px;
    height: 40px;
    font-size: 1.2rem;
  }
  .card {
    padding: 15px;
  }
  .formula-display,
  .go-button {
    font-size: 1.2rem;
    padding: 15px 20px;
  }
  .formula-display {
    height: 60px;
  }
  .go-button {
    height: 60px;
  }
}
</style>