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
const errorMessage = document.getElementById('errorMessage');

let currentFile = null;
let currentImageFilename = null;
let latestResult = null;
let isSubmitting = false;  // Prevent double submissions

function setButtonState() {
  predictBtn.disabled = !currentFile || isSubmitting;
  resetBtn.disabled = !currentFile;
  downloadReportBtn.disabled = !latestResult;
}

function showErrorInline(message) {
  if (errorMessage) {
    errorMessage.textContent = message;
    errorMessage.style.display = 'block';
    setTimeout(() => {
      errorMessage.style.display = 'none';
    }, 5000);
  }
}

function resetPreview() {
  currentFile = null;
  currentImageFilename = null;
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
  errorMessage.style.display = 'none';
  setButtonState();
}

function updatePreview(file) {
  const reader = new FileReader();
  reader.onload = () => {
    previewImage.src = reader.result;
    previewImage.classList.remove('hidden');
    previewPlaceholder.classList.add('hidden');
    currentFile = file;
    currentImageFilename = file.name;
    emptyState.classList.add('hidden');
    loadingState.classList.add('hidden');
    resultSummary.classList.add('hidden');
    latestResult = null;
    errorMessage.style.display = 'none';
    setButtonState();
  };
  reader.readAsDataURL(file);
}

function showLoading() {
  emptyState.classList.add('hidden');
  resultSummary.classList.add('hidden');
  loadingState.classList.remove('hidden');
  errorMessage.style.display = 'none';
}

function showResult(data) {
  diseaseName.textContent = data.prediction;
  confidenceScore.textContent = `${Number(data.confidence).toFixed(2)}%`;
  predictionDate.textContent = data.date;
  diseaseDescription.textContent = data.description;
  
  const confidencePercent = Number(data.confidence);
  confidenceBar.style.width = `${confidencePercent}%`;
  confidenceBar.style.background = confidencePercent > 50 ? '#22c55e' : '#f59e0b';

  const severity = data.severity || 'Normal';
  severityBadge.textContent = severity;
  
  // Map severity to badge class
  const severityLower = severity.toLowerCase();
  if (severityLower.includes('high')) {
    severityBadge.className = 'severity-badge badge-high';
  } else if (severityLower.includes('medium')) {
    severityBadge.className = 'severity-badge badge-medium';
  } else if (severityLower.includes('severe')) {
    severityBadge.className = 'severity-badge badge-severe';
  } else {
    severityBadge.className = 'severity-badge badge-normal';
  }
  
  loadingState.classList.add('hidden');
  emptyState.classList.add('hidden');
  resultSummary.classList.remove('hidden');
  setButtonState();
}

function showError(message) {
  showErrorInline(message);
  emptyState.classList.remove('hidden');
  loadingState.classList.add('hidden');
  resultSummary.classList.add('hidden');
}

async function submitPrediction() {
  if (!currentFile) {
    showErrorInline('Please select an image first.');
    return;
  }

  // Prevent double submissions
  if (isSubmitting) {
    showErrorInline('Request already in progress. Please wait...');
    return;
  }

  isSubmitting = true;
  setButtonState();
  showLoading();

  const formData = new FormData();
  formData.append('image', currentFile);

  try {
    const response = await fetch('/predict', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();

    if (!response.ok || !data.success) {
      if (response.status === 401) {
        window.location.href = '/login';
        return;
      }
      showError(data.error || 'Prediction failed. Please try another image.');
      isSubmitting = false;
      setButtonState();
      return;
    }

    // Successfully received prediction
    latestResult = {
      prediction: data.prediction,
      confidence: data.confidence,
      severity: data.severity,
      description: data.description,
      date: data.date,
      filename: data.filename,
      prediction_id: data.prediction_id
    };

    showResult(latestResult);
    isSubmitting = false;
    setButtonState();
  } catch (error) {
    console.error('Fetch error:', error);
    showError('Unable to complete prediction. Please try again later.');
    isSubmitting = false;
    setButtonState();
  }
}

function buildReport() {
  if (!latestResult) {
    showErrorInline('No prediction available. Please make a prediction first.');
    return;
  }
  const imageParam = latestResult.filename ? `&image=${encodeURIComponent(latestResult.filename)}` : '';
  const params = new URLSearchParams({
    disease: latestResult.prediction,
    confidence: Number(latestResult.confidence).toFixed(2),
    severity: latestResult.severity || 'Normal',
    date: latestResult.date,
  });

  window.location.href = `/download_report?${params.toString()}${imageParam}`;
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
    showErrorInline('Invalid image format. Only JPG and PNG retinal images are supported.');
    previewInput.value = '';
    return;
  }

  const MAX_SIZE = 10 * 1024 * 1024; // 10MB
  if (file.size > MAX_SIZE) {
    showErrorInline('Image size is too large. Please upload an image smaller than 10MB.');
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
  
  const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
  if (!validTypes.includes(file.type)) {
    showErrorInline('Invalid image format. Only JPG and PNG retinal images are supported.');
    return;
  }

  previewInput.files = event.dataTransfer.files;
  updatePreview(file);
});

resetPreview();
