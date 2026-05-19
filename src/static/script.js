document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');
    
    // Image Elements
    const imageInput = document.getElementById('imageInput');
    const imageUploadArea = document.getElementById('imageUploadArea');
    const imagePreview = document.getElementById('imagePreview');
    
    // Video Elements
    const videoInput = document.getElementById('videoInput');
    const videoUploadArea = document.getElementById('videoUploadArea');
    const videoPreview = document.getElementById('videoPreview');
    const youtubeInput = document.getElementById('youtubeInput');
    const youtubePreviewContainer = document.getElementById('youtubePreviewContainer');
    
    // Common Elements
    const questionInput = document.getElementById('questionInput');
    const submitBtn = document.getElementById('submitBtn');
    
    // Result Cards
    const loading = document.getElementById('loading');
    const answerBox = document.getElementById('answerBox');
    const answerText = document.getElementById('answerText');
    const errorBox = document.getElementById('errorBox');
    const errorText = document.getElementById('errorText');
    
    // Metrics
    const metricModel = document.getElementById('metricModel');
    const metricType = document.getElementById('metricType');
    const metricTime = document.getElementById('metricTime');
    
    // History
    const historyList = document.getElementById('historyList');
    const historyCount = document.getElementById('historyCount');
    const clearHistoryBtn = document.getElementById('clearHistoryBtn');

    // App State
    let currentTab = 'image'; // 'image' or 'video'
    let imageFile = null;
    let videoFile = null;
    let youtubeUrl = '';
    let history = [];

    // Initialize marked options
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    // -------------------------------------------------------------
    // History & Sidebar Caching Functions
    // -------------------------------------------------------------
    function loadHistory() {
        const cached = localStorage.getItem('vqa_dashboard_history');
        if (cached) {
            try {
                history = JSON.parse(cached);
            } catch (err) {
                history = [];
            }
        }
        updateHistoryUI();
    }

    function saveHistory() {
        localStorage.setItem('vqa_dashboard_history', JSON.stringify(history));
        updateHistoryUI();
    }

    function addHistoryItem(item) {
        // Prevent duplicate questions in recent history (optional, let's keep it simple: insert at start)
        history.unshift(item);
        if (history.length > 20) {
            history.pop();
        }
        saveHistory();
    }

    function updateHistoryUI() {
        historyCount.textContent = history.length;
        if (history.length === 0) {
            historyList.innerHTML = `
                <div class="history-empty">
                    <p>No queries yet</p>
                    <span>Analyze images or videos to build your history log</span>
                </div>
            `;
            return;
        }

        historyList.innerHTML = '';
        history.forEach((item, idx) => {
            const date = new Date(item.timestamp);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            // Icon selection
            let iconSvg = '';
            if (item.tab === 'image') {
                iconSvg = `<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>`;
            } else if (item.youtubeUrl) {
                iconSvg = `<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M23.498 6.163a3.003 3.003 0 0 0-2.11-2.11C19.517 3.545 12 3.545 12 3.545s-7.517 0-9.388.508a3.003 3.003 0 0 0-2.11 2.11C0 8.033 0 12 0 12s0 3.967.502 5.837a3.003 3.003 0 0 0 2.11 2.11c1.871.508 9.388.508 9.388.508s7.517 0 9.388-.508a3.003 3.003 0 0 0 2.11-2.11C24 15.967 24 12 24 12s0-3.967-.502-5.837zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>`;
            } else {
                iconSvg = `<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg>`;
            }

            const itemDiv = document.createElement('div');
            itemDiv.className = 'history-item';
            itemDiv.innerHTML = `
                <div class="item-icon">${iconSvg}</div>
                <div class="item-content">
                    <div class="item-question">${escapeHTML(item.question)}</div>
                    <div class="item-time">${timeStr}</div>
                </div>
            `;

            itemDiv.addEventListener('click', () => {
                restoreHistoryState(item);
            });

            historyList.appendChild(itemDiv);
        });
    }

    function restoreHistoryState(item) {
        // Reset inputs
        errorBox.style.display = 'none';
        
        // Restore tab
        currentTab = item.tab;
        tabBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === currentTab);
        });
        tabPanels.forEach(panel => {
            panel.classList.toggle('active', panel.id === `${currentTab}Panel`);
        });

        // Restore question
        questionInput.value = item.question;

        // Restore media preview
        if (currentTab === 'image') {
            imageFile = null; // cached state doesn't hold direct file handle
            imageInput.value = '';
            imagePreview.src = item.mediaSrc;
            imagePreview.style.display = 'block';
            imageUploadArea.querySelector('.placeholder-text').style.display = 'none';
            imageUploadArea.classList.add('has-file');
        } else {
            videoFile = null;
            videoInput.value = '';
            
            if (item.youtubeUrl) {
                youtubeUrl = item.youtubeUrl;
                youtubeInput.value = youtubeUrl;
                
                const ytId = extractYouTubeId(youtubeUrl);
                if (ytId) {
                    youtubePreviewContainer.innerHTML = `<iframe src="https://www.youtube.com/embed/${ytId}" allowfullscreen></iframe>`;
                    youtubePreviewContainer.style.display = 'block';
                    videoUploadArea.style.display = 'none';
                }
            } else {
                youtubeUrl = '';
                youtubeInput.value = '';
                youtubePreviewContainer.style.display = 'none';
                videoUploadArea.style.display = 'flex';
                
                // Show localized placeholder for historical video file
                videoPreview.style.display = 'none';
                videoUploadArea.classList.remove('has-file');
                videoUploadArea.querySelector('.placeholder-text').style.display = 'block';
                videoUploadArea.querySelector('.placeholder-text p').textContent = item.mediaSrc || "Local Video Uploaded";
                videoUploadArea.querySelector('.placeholder-text .upload-sub').textContent = "Click to replace video file";
            }
        }

        // Restore answer
        renderMarkdown(item.answer);
        
        // Restore metrics
        metricModel.textContent = item.metrics.model;
        metricType.textContent = item.metrics.type;
        metricTime.textContent = item.metrics.time;
        metricsBadge.style.display = 'flex';
        
        answerBox.style.display = 'block';
        answerBox.scrollIntoView({ behavior: 'smooth' });
    }

    clearHistoryBtn.addEventListener('click', () => {
        if (confirm("Are you sure you want to clear your query history?")) {
            history = [];
            saveHistory();
        }
    });

    // Helpers
    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
        );
    }

    function extractYouTubeId(url) {
        const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
        const match = url.match(regExp);
        return (match && match[2].length === 11) ? match[2] : null;
    }

    // -------------------------------------------------------------
    // Navigation / Tab Switching
    // -------------------------------------------------------------
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => p.classList.remove('active'));
            
            btn.classList.add('active');
            currentTab = btn.dataset.tab;
            
            const targetPanel = document.getElementById(`${currentTab}Panel`);
            if (targetPanel) {
                targetPanel.classList.add('active');
            }
        });
    });

    // -------------------------------------------------------------
    // Image Media Upload Logic
    // -------------------------------------------------------------
    imageUploadArea.addEventListener('click', () => {
        imageInput.click();
    });

    // Drag-Drop events for Image
    ['dragenter', 'dragover'].forEach(eventName => {
        imageUploadArea.addEventListener(eventName, (e) => {
            e.preventDefault();
            imageUploadArea.style.borderColor = 'var(--primary)';
            imageUploadArea.style.background = 'rgba(99, 102, 241, 0.04)';
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        imageUploadArea.addEventListener(eventName, (e) => {
            e.preventDefault();
            imageUploadArea.style.borderColor = 'var(--glass-border)';
            imageUploadArea.style.background = 'var(--bg-glass)';
        }, false);
    });

    imageUploadArea.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
            handleImageSelection(file);
        }
    });

    imageInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleImageSelection(file);
        }
    });

    function handleImageSelection(file) {
        imageFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            imagePreview.style.display = 'block';
            imageUploadArea.querySelector('.placeholder-text').style.display = 'none';
            imageUploadArea.classList.add('has-file');
        };
        reader.readAsDataURL(file);
    }

    // -------------------------------------------------------------
    // Video Media Upload Logic
    // -------------------------------------------------------------
    videoUploadArea.addEventListener('click', () => {
        videoInput.click();
    });

    // Drag-Drop events for Video
    ['dragenter', 'dragover'].forEach(eventName => {
        videoUploadArea.addEventListener(eventName, (e) => {
            e.preventDefault();
            videoUploadArea.style.borderColor = 'var(--primary)';
            videoUploadArea.style.background = 'rgba(99, 102, 241, 0.04)';
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        videoUploadArea.addEventListener(eventName, (e) => {
            e.preventDefault();
            videoUploadArea.style.borderColor = 'var(--glass-border)';
            videoUploadArea.style.background = 'var(--bg-glass)';
        }, false);
    });

    videoUploadArea.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('video/')) {
            handleVideoSelection(file);
        }
    });

    videoInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleVideoSelection(file);
        }
    });

    function handleVideoSelection(file) {
        videoFile = file;
        
        // Reset YouTube if local video is selected
        youtubeInput.value = '';
        youtubeUrl = '';
        youtubePreviewContainer.style.display = 'none';
        videoUploadArea.style.display = 'flex';

        const fileURL = URL.createObjectURL(file);
        videoPreview.src = fileURL;
        videoPreview.style.display = 'block';
        videoUploadArea.querySelector('.placeholder-text').style.display = 'none';
        videoUploadArea.classList.add('has-file');
    }

    // YouTube Input Change Logic
    youtubeInput.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        youtubeUrl = val;

        if (val) {
            const ytId = extractYouTubeId(val);
            if (ytId) {
                // Clear local video preview
                videoFile = null;
                videoInput.value = '';
                videoPreview.src = '';
                videoPreview.style.display = 'none';
                
                // Switch area layout
                videoUploadArea.style.display = 'none';
                youtubePreviewContainer.innerHTML = `<iframe src="https://www.youtube.com/embed/${ytId}" allowfullscreen></iframe>`;
                youtubePreviewContainer.style.display = 'block';
            } else {
                youtubePreviewContainer.style.display = 'none';
                videoUploadArea.style.display = 'flex';
            }
        } else {
            youtubePreviewContainer.style.display = 'none';
            videoUploadArea.style.display = 'flex';
        }
    });

    // -------------------------------------------------------------
    // Core Prediction Submission logic
    // -------------------------------------------------------------
    submitBtn.addEventListener('click', async () => {
        const question = questionInput.value.trim();

        // 1. Reset alert and result cards
        errorBox.style.display = 'none';
        answerBox.style.display = 'none';

        // 2. Client Side Validations
        if (!question) {
            showError("Please ask a detailed question about the media.");
            return;
        }

        const formData = new FormData();
        formData.append('question', question);

        let mediaCacheSrc = ''; // Base64 or local filename representation for local storage history

        if (currentTab === 'image') {
            if (!imageFile && !imageUploadArea.classList.contains('has-file')) {
                showError("Please upload an image first.");
                return;
            }
            if (imageFile) {
                formData.append('image', imageFile);
                mediaCacheSrc = imagePreview.src;
            } else {
                // Restored from history
                showError("Please upload a new image to execute analysis.");
                return;
            }
        } else {
            // Video Modality
            if (youtubeUrl) {
                const ytId = extractYouTubeId(youtubeUrl);
                if (!ytId) {
                    showError("Invalid YouTube URL format.");
                    return;
                }
                formData.append('youtube_url', youtubeUrl);
            } else {
                if (!videoFile && !videoUploadArea.classList.contains('has-file')) {
                    showError("Please upload a video file or paste a valid YouTube link.");
                    return;
                }
                if (videoFile) {
                    formData.append('video', videoFile);
                    mediaCacheSrc = videoFile.name;
                } else {
                    // Restored from history
                    showError("Please upload a new video file to execute analysis.");
                    return;
                }
            }
        }

        // 3. Display Loading Skeleton
        loading.style.display = 'block';
        loading.scrollIntoView({ behavior: 'smooth' });

        try {
            const response = await fetch('/predict', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            loading.style.display = 'none';

            if (response.ok) {
                // Render rich Markdown response
                renderMarkdown(data.answer);

                // Populate metrics
                metricModel.textContent = data.metrics.model;
                metricType.textContent = data.metrics.type;
                metricTime.textContent = data.metrics.time;
                metricsBadge.style.display = 'flex';

                answerBox.style.display = 'block';
                answerBox.scrollIntoView({ behavior: 'smooth' });

                // Cache to sidebar history log
                const historyObj = {
                    id: Date.now(),
                    tab: currentTab,
                    mediaSrc: currentTab === 'image' ? mediaCacheSrc : (youtubeUrl ? '' : mediaCacheSrc),
                    youtubeUrl: youtubeUrl || '',
                    question: question,
                    answer: data.answer,
                    metrics: data.metrics,
                    timestamp: new Date().toISOString()
                };
                addHistoryItem(historyObj);

            } else {
                showError(data.error || "A processing error occurred.");
            }
        } catch (err) {
            loading.style.display = 'none';
            showError("Failed to establish contact with local VQA Server.");
        }
    });

    // Markdown parse renderer
    function renderMarkdown(mdText) {
        answerText.innerHTML = marked.parse(mdText);
    }

    function showError(msg) {
        errorText.textContent = msg;
        errorBox.style.display = 'flex';
        errorBox.scrollIntoView({ behavior: 'smooth' });
    }

    // -------------------------------------------------------------
    // Boot Initialization
    // -------------------------------------------------------------
    loadHistory();
});
