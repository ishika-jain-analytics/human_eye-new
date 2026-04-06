const dropzone = document.getElementById('dropzone');
const chooseImageBtn = document.getElementById('chooseImageBtn');
const resetBtn = document.getElementById('resetBtn');
const predictBtn = document.getElementById('predictBtn');
const downloadReportBtn = document.getElementById('downloadReportBtn');
const previewInput = document.getElementById('eyeImage');
const previewImage = document.getElementById('previewImage');
const previewPlaceholder = document.getElementById('previewPlaceholder');
const emptyState = document.getElementById('emptyState');
const loadingState = document.getElementById('loadingState');
const resultSummary = document.getElementById('resultSummary');
const diseaseName = document.getElementById('diseaseName');
const confidenceScore = document.getElementById('confidenceScore');
const confidenceBar = document.getElementById('confidenceBar');
const severityBadge = document.getElementById('severityBadge');
const diseaseDescription = document.getElementById('diseaseDescription');
const predictionDate = document.getElementById('predictionDate');

let currentFile = null;
let latestResult = null;

function setButtonState() {
  predictBtn.disabled = !currentFile;
  resetBtn.disabled = !currentFile;
  downloadReportBtn.disabled = !latestResult;
}

function resetPreview() {
  currentFile = null;
  latestResult = null;
  previewImage.src = '';
  previewImage.classList.add('hidden');
  previewPlaceholder.classList.remove('hidden');
  emptyState.classList.remove('hidden');
  loadingState.classList.add('hidden');
  resultSummary.classList.add('hidden');
  diseaseName.textContent = '-';
  confidenceScore.textContent = '-';
  confidenceBar.style.width = '0%';
  confidenceBar.style.background = '#f59e0b';
  severityBadge.textContent = 'Normal';
  severityBadge.className = 'severity-badge badge-normal';
  diseaseDescription.textContent = '-';
  predictionDate.textContent = '-';
  setButtonState();
}

function updatePreview(file) {
  const reader = new FileReader();
  reader.onload = () => {
    previewImage.src = reader.result;
    previewImage.classList.remove('hidden');
    previewPlaceholder.classList.add('hidden');
    currentFile = file;
    emptyState.classList.add('hidden');
    loadingState.classList.add('hidden');
    resultSummary.classList.add('hidden');
    latestResult = null;
    setButtonState();
  };
  reader.readAsDataURL(file);
}

function showLoading() {
  emptyState.classList.add('hidden');
  resultSummary.classList.add('hidden');
  loadingState.classList.remove('hidden');
}

function showResult(data) {
  latestResult = data;
  diseaseName.textContent = data.prediction;
  confidenceScore.textContent = `${data.confidence.toFixed(2)}%`;
  predictionDate.textContent = data.date;
  diseaseDescription.textContent = data.description;
  const confidencePercent = data.confidence;
  confidenceBar.style.width = `${confidencePercent}%`;
  confidenceBar.style.background = confidencePercent > 50 ? '#22c55e' : '#f59e0b';

  const severity = data.severity || 'Normal';
  severityBadge.textContent = severity;
  severityBadge.className = `severity-badge ${severity.toLowerCase()}`;
  
  loadingState.classList.add('hidden');
  emptyState.classList.add('hidden');
  resultSummary.classList.remove('hidden');
  setButtonState();
}

function showError(message) {
  emptyState.querySelector('p').textContent = message;
  emptyState.classList.remove('hidden');
  loadingState.classList.add('hidden');
  resultSummary.classList.add('hidden');
}

async function submitPrediction() {
  if (!currentFile) return;
  showLoading();

  const formData = new FormData();
  formData.append('image', currentFile);

  try {
    const response = await fetch('/predict', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      if (response.status === 401) {
        window.location.href = '/login';
        return;
      }
      showError(data.error || 'Prediction failed. Please try another image.');
      return;
    }

    showResult(data);
  } catch (error) {
    showError('Unable to complete prediction. Please try again later.');
    console.error(error);
  }
}

function buildReport() {
  if (!latestResult) return;
  const params = new URLSearchParams({
    disease: latestResult.prediction,
    confidence: latestResult.confidence.toFixed(2),
    severity: latestResult.severity || 'Normal',
    date: latestResult.date,
  });

  window.location.href = `/download_report?${params.toString()}`;
}

chooseImageBtn.addEventListener('click', () => previewInput.click());
resetBtn.addEventListener('click', resetPreview);
predictBtn.addEventListener('click', submitPrediction);
downloadReportBtn.addEventListener('click', buildReport);

dropzone.addEventListener('click', () => previewInput.click());

previewInput.addEventListener('change', (event) => {
  const file = event.target.files[0];
  if (!file) return;

  const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
  if (!validTypes.includes(file.type)) {
    showError('Invalid image format. Please upload JPG, JPEG, or PNG.');
    previewInput.value = '';
    return;
  }

  updatePreview(file);
});

['dragenter', 'dragover'].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    event.stopPropagation();
    dropzone.classList.add('drag-over');
  });
});

dropzone.addEventListener('dragleave', (event) => {
  event.preventDefault();
  event.stopPropagation();
  dropzone.classList.remove('drag-over');
});

dropzone.addEventListener('drop', (event) => {
  event.preventDefault();
  event.stopPropagation();
  dropzone.classList.remove('drag-over');

  const file = event.dataTransfer.files[0];
  if (!file) return;
  previewInput.files = event.dataTransfer.files;
  updatePreview(file);
});

resetPreview();
