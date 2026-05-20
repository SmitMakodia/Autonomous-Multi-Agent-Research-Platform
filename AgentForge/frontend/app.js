const canvas = document.getElementById('bg-canvas');
const ctx = canvas.getContext('2d');

let width, height;
let particles = [];
const mouse = { x: null, y: null, radius: 150 };

function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

window.addEventListener('mousemove', (e) => {
    mouse.x = e.x;
    mouse.y = e.y;
});
window.addEventListener('mouseout', () => {
    mouse.x = null;
    mouse.y = null;
});

class Particle {
    constructor() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.size = Math.random() * 2 + 0.5;
        this.speedX = Math.random() * 1 - 0.5;
        this.speedY = Math.random() * 1 - 0.5;
        this.baseColor = Math.random() > 0.5 ? '#00d2ff' : '#3a7bd5';
    }
    update() {
        this.x += this.speedX;
        this.y += this.speedY;

        if (this.x > width) this.x = 0;
        if (this.x < 0) this.x = width;
        if (this.y > height) this.y = 0;
        if (this.y < 0) this.y = height;

        if (mouse.x != null) {
            let dx = mouse.x - this.x;
            let dy = mouse.y - this.y;
            let distance = Math.sqrt(dx * dx + dy * dy);
            if (distance < mouse.radius) {
                const forceDirectionX = dx / distance;
                const forceDirectionY = dy / distance;
                const force = (mouse.radius - distance) / mouse.radius;
                this.x -= forceDirectionX * force * 3;
                this.y -= forceDirectionY * force * 3;
            }
        }
    }
    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = this.baseColor;
        ctx.globalAlpha = 0.6;
        ctx.fill();
    }
}

function initParticles() {
    particles = [];
    const numParticles = (width * height) / 12000;
    for (let i = 0; i < numParticles; i++) {
        particles.push(new Particle());
    }
}

function animateParticles() {
    ctx.clearRect(0, 0, width, height);
    for (let i = 0; i < particles.length; i++) {
        particles[i].update();
        particles[i].draw();
        
        for (let j = i; j < particles.length; j++) {
            const dx = particles[i].x - particles[j].x;
            const dy = particles[i].y - particles[j].y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            
            if (distance < 120) {
                ctx.beginPath();
                ctx.strokeStyle = '#00d2ff';
                ctx.globalAlpha = 1 - (distance / 120);
                ctx.lineWidth = 0.5;
                ctx.moveTo(particles[i].x, particles[i].y);
                ctx.lineTo(particles[j].x, particles[j].y);
                ctx.stroke();
            }
        }
    }
    requestAnimationFrame(animateParticles);
}
initParticles();
animateParticles();

const promptInput = document.getElementById('prompt-input');
const chatThread = document.getElementById('chat-thread');
const fileInput = document.getElementById('file-input');
const fileList = document.getElementById('file-list');
const agentStatusList = document.getElementById('agent-status-list');
const sendBtn = document.getElementById('send-btn');
const stopBtn = document.getElementById('stop-btn');
const welcomeScreen = document.getElementById('welcome-screen');

let sessionId = null;
let currentFiles = [];
let activeEventSource = null;

// Initialize session ID from URL if present
const pathParts = window.location.pathname.split('/').filter(p => p);
if (pathParts.length > 0 && pathParts[0] !== 'index.html' && pathParts[0] !== 'app.js' && pathParts[0] !== 'style.css') {
    sessionId = pathParts[0];
}

marked.setOptions({
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
        }
        return hljs.highlightAuto(code).value;
    }
});

const allowedExtensions = ['.pdf', '.docx', '.pptx', '.xlsx', '.csv', '.txt', '.json', '.md', '.png', '.jpg', '.jpeg', '.webp'];
let popupTimeout = null;

function showFilePopup(filename) {
    const popup = document.getElementById('file-popup');
    const msg = document.getElementById('popup-message');
    const timer = document.getElementById('popup-timer');
    
    msg.textContent = `The file "${filename}" has an unsupported format. Please upload one of the following: PDF, DOCX, PPTX, XLSX, CSV, TXT, JSON, MD, PNG, JPG.`;
    popup.style.display = 'block';
    
    timer.style.animation = 'none';
    timer.offsetHeight; 
    timer.style.animation = null;

    if (popupTimeout) clearTimeout(popupTimeout);
    popupTimeout = setTimeout(() => {
        popup.style.display = 'none';
    }, 10000);
}

document.getElementById('popup-close-btn').addEventListener('click', () => {
    document.getElementById('file-popup').style.display = 'none';
    if (popupTimeout) clearTimeout(popupTimeout);
});

document.getElementById('context-close-btn').addEventListener('click', () => {
    document.getElementById('context-modal').style.display = 'none';
});

function updateFileListUI() {
    fileList.innerHTML = '';
    currentFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
            <span>${file.name}</span>
            <button type="button" class="remove-file-btn" data-index="${index}">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        `;
        fileList.appendChild(fileItem);
    });

    document.querySelectorAll('.remove-file-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = parseInt(e.currentTarget.getAttribute('data-index'));
            currentFiles.splice(idx, 1);
            updateFileListUI();
        });
    });
}

function handleFileSelection(files) {
    if (!files || files.length === 0) return;
    
    for (let file of files) {
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (!allowedExtensions.includes(ext)) {
            showFilePopup(file.name);
            continue;
        }
        currentFiles.push(file);
    }
    fileInput.value = '';
    updateFileListUI();
}

fileInput.addEventListener('change', (e) => {
    handleFileSelection(e.target.files);
});

promptInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

function hideWelcomeScreen() {
    if (welcomeScreen && welcomeScreen.style.display !== 'none') {
        welcomeScreen.style.display = 'none';
    }
}

function addCopyButtons(container) {
    // Add to code blocks
    container.querySelectorAll('pre').forEach(pre => {
        if (pre.querySelector('.copy-code-btn')) return;
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-code-btn';
        copyBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
        copyBtn.title = "Copy code";
        pre.style.position = 'relative';
        pre.appendChild(copyBtn);
        
        copyBtn.addEventListener('click', () => {
            const code = pre.querySelector('code').innerText;
            navigator.clipboard.writeText(code);
            copyBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#00e676" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
            setTimeout(() => {
                copyBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
            }, 2000);
        });
    });
}

function appendMessage(role, content) {
    hideWelcomeScreen();

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    
    let innerHTML = '';

    if (role === 'assistant') {
        innerHTML = `
            <div class="assistant-header">
                <div class="avatar-icon">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 22h20L12 2z"/></svg>
                </div>
            </div>
            <div class="message-content"></div>
            <div class="message-actions" style="display:none;">
                <button class="copy-msg-btn" title="Copy full response">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    Copy
                </button>
                <button class="view-sources-btn" style="display:none;" title="View Context">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                    Context
                </button>
            </div>
            <div class="message-extras"></div>
        `;
    } else {
        innerHTML = `
            <div class="message-content"></div>
        `;
    }

    msgDiv.innerHTML = innerHTML;
    chatThread.appendChild(msgDiv);

    const contentDiv = msgDiv.querySelector('.message-content');
    
    if (role === 'assistant') {
        const parsedHtml = marked.parse(content);
        contentDiv.innerHTML = parsedHtml;
        contentDiv.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
        addCopyButtons(contentDiv);

        const copyMsgBtn = msgDiv.querySelector('.copy-msg-btn');
        copyMsgBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(content);
            copyMsgBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#00e676" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!';
            setTimeout(() => {
                copyMsgBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Copy';
            }, 2000);
        });

    } else {
        contentDiv.textContent = content;
        contentDiv.style.whiteSpace = "pre-wrap";
    }

    chatThread.scrollTop = chatThread.scrollHeight;
    
    return { 
        msgDiv,
        contentDiv, 
        thinkingContent: msgDiv.querySelector('.thinking-content'), 
        thinkingContainer: msgDiv.querySelector('.thinking-process'),
        messageActions: msgDiv.querySelector('.message-actions'),
        messageExtras: msgDiv.querySelector('.message-extras')
    };
}

async function loadSessions() {
    try {
        const res = await fetch('/api/sessions');
        if (res.ok) {
            const data = await res.json();
            const list = document.getElementById('session-list');
            list.innerHTML = '';
            data.sessions.forEach(session => {
                const li = document.createElement('li');
                
                const titleSpan = document.createElement('span');
                titleSpan.textContent = session.title;
                
                const delBtn = document.createElement('button');
                delBtn.className = 'delete-session-btn';
                delBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>';
                delBtn.title = "Delete Thread";
                
                delBtn.onclick = async (e) => {
                    e.stopPropagation();
                    if(confirm(`Delete thread: ${session.title}?`)) {
                        await fetch(`/api/sessions/${session.id}`, { method: 'DELETE' });
                        if (sessionId === session.id) {
                            document.getElementById('new-chat-btn').click();
                        } else {
                            loadSessions();
                        }
                    }
                };

                li.appendChild(titleSpan);
                li.appendChild(delBtn);

                li.onclick = () => {
                    window.history.pushState(null, '', '/' + session.id);
                    loadSessionHistory(session.id);
                };
                
                if (sessionId === session.id) {
                    li.classList.add('active');
                }
                
                list.appendChild(li);
            });
        }
    } catch (e) {
        console.error("Failed to load sessions", e);
    }
}

async function loadSessionHistory(id) {
    try {
        const res = await fetch(`/api/sessions/${id}`);
        if (res.ok) {
            const data = await res.json();
            const threadMsgs = document.querySelectorAll('.message');
            threadMsgs.forEach(m => m.remove());
            sessionId = id;
            hideWelcomeScreen();
            
            data.messages.forEach(msg => {
                const { contentDiv: responseContainer, thinkingContainer, thinkingContent, messageActions, msgDiv, messageExtras } = appendMessage(msg.role, msg.content);
                if (msg.role === 'assistant') {
                    if (msg.reasoning) {
                        thinkingContainer.style.display = 'block';
                        thinkingContent.classList.add('finished');
                        thinkingContent.innerHTML = marked.parse(msg.reasoning);
                    }
                    
                    if (msg.sources) {
                        try {
                            const parsedSources = JSON.parse(msg.sources);
                            if (parsedSources && parsedSources.length > 0) {
                                let sourcesHtml = `<div class="sources-container"><div class="sources-title">Sources</div><div class="sources-list">`;
                                parsedSources.forEach(s => {
                                    let domain = s;
                                    try {
                                        const url = new URL(s);
                                        domain = url.hostname;
                                    } catch(e) {}
                                    
                                    sourcesHtml += `
                                        <a href="${s}" target="_blank" class="source-card" title="${s}">
                                            <div class="source-icon"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"></path><polyline points="16 3 21 3 21 8"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg></div>
                                            <div class="source-details">
                                                <div class="source-domain">${domain}</div>
                                            </div>
                                        </a>`;
                                });
                                sourcesHtml += `</div></div>`;
                                if (messageExtras) messageExtras.innerHTML += sourcesHtml;
                            }
                        } catch(e) {}
                    }
                    
                    if (msg.context) {
                        let contextHtml = `
                            <div class="rag-context-block" style="margin-top: 20px; padding: 16px; border-left: 2px solid rgba(255,255,255,0.1); color: var(--color-text-muted); font-size: 0.85rem; max-height: 200px; overflow-y: auto;">
                                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                                    Extracted Context
                                </div>
                                <div style="white-space: pre-wrap; font-family: var(--font-mono); opacity: 0.8;">${msg.context}</div>
                            </div>
                        `;
                        if (messageExtras) messageExtras.innerHTML += contextHtml;
                    }
                    
                    if (messageActions) {
                        messageActions.style.display = 'flex';
                        msgDiv.querySelector('.copy-msg-btn').onclick = () => {
                            navigator.clipboard.writeText(msg.content);
                            const btn = msgDiv.querySelector('.copy-msg-btn');
                            btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#00e676" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!';
                            setTimeout(() => {
                                btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Copy';
                            }, 2000);
                        };
                    }
                }
            });
            chatThread.scrollTop = chatThread.scrollHeight;
            loadSessions(); // to update active state
        }
    } catch (e) {
        console.error("Failed to load history", e);
    }
}

document.getElementById('new-chat-btn').addEventListener('click', () => {
    sessionId = null;
    window.history.pushState(null, '', '/');
    const threadMsgs = document.querySelectorAll('.message');
    threadMsgs.forEach(m => m.remove());
    welcomeScreen.style.display = 'block';
    loadSessions(); // to remove active state
});

window.addEventListener('DOMContentLoaded', () => {
    loadSessions();
    if (sessionId) {
        loadSessionHistory(sessionId);
    }
});

function updateAgentStatus(statusText, state = 'running') {
    const li = document.createElement('li');
    li.className = state;
    li.innerHTML = `
        <div class="agent-icon ${state}">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line>
            </svg>
        </div>
        <span>${statusText}</span>
    `;
    
    if (agentStatusList.children.length > 2) {
        agentStatusList.removeChild(agentStatusList.firstChild);
    }
    
    agentStatusList.appendChild(li);
    
    if (state === 'done' || state === 'error' || state === 'stopped') {
        setTimeout(() => {
            if (agentStatusList.contains(li)) {
                li.style.opacity = '0';
                setTimeout(() => li.remove(), 300);
            }
        }, 5000);
    }
}

stopBtn.addEventListener('click', () => {
    if (activeEventSource) {
        activeEventSource.close();
        activeEventSource = null;
        updateAgentStatus('User interrupted', 'stopped');
        sendBtn.style.display = 'flex';
        stopBtn.style.display = 'none';
        
        const lastMsg = document.querySelector('.message.assistant:last-child .message-content');
        if (lastMsg) {
            lastMsg.innerHTML += `<br><br><span style="color:var(--color-warning); font-size: 0.85em; font-style: italic;">[Inference stopped by user]</span>`;
            chatThread.scrollTop = chatThread.scrollHeight;
        }
        
        const lastActions = document.querySelector('.message.assistant:last-child .message-actions');
        if (lastActions) lastActions.style.display = 'flex';
        
        const lastThinking = document.querySelector('.message.assistant:last-child .thinking-content');
        if (lastThinking) lastThinking.classList.add('finished');
    }
});

async function handlePromptSubmit(e) {
    if (e && e.preventDefault) {
        e.preventDefault();
    }
    
    const prompt = promptInput.value.trim();
    if (!prompt && currentFiles.length === 0) return;
    
    let userMsg = prompt;
    if (currentFiles.length > 0) {
        const fileNames = currentFiles.map(f => f.name).join(', ');
        userMsg = `[Attached: ${fileNames}]\n` + userMsg;
    }
    appendMessage('user', userMsg);
    
    promptInput.value = '';
    promptInput.style.height = 'auto';
    
    const formData = new FormData();
    formData.append('prompt', prompt || "Process the attached files.");
    if (sessionId) formData.append('session_id', sessionId);
    
    if (currentFiles.length > 0) {
        currentFiles.forEach(file => {
            formData.append('files', file);
        });
        currentFiles = [];
        updateFileListUI();
    }
    
    updateAgentStatus('Orchestrating swarm...', 'running');
    
    sendBtn.style.display = 'none';
    stopBtn.style.display = 'flex';
    
    const { contentDiv: responseContainer, thinkingContent, thinkingContainer, messageActions, messageExtras, msgDiv } = appendMessage('assistant', '');
    let fullResponse = '';
    let fullReasoning = '';
    let firstTokenReceived = false;
    
    try {
        const res = await fetch('/api/query', {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) throw new Error("Failed to submit query");
        
        const data = await res.json();
        sessionId = data.session_id;
        const queryId = data.query_id;
        
        window.history.pushState(null, '', '/' + sessionId);
        loadSessions(); // update session list right away
        
        activeEventSource = new EventSource(`/api/stream/${queryId}`);
        
        activeEventSource.onmessage = (e) => {
            try {
                const parsed = JSON.parse(e.data);
                
                if (parsed.event === 'status') {
                    updateAgentStatus(parsed.data, 'running');
                } 
                else if (parsed.event === 'reasoning') {
                    thinkingContainer.style.display = 'block';
                    fullReasoning += parsed.data;
                    thinkingContent.innerHTML = marked.parse(fullReasoning);
                    if (!firstTokenReceived) {
                        thinkingContent.scrollTop = thinkingContent.scrollHeight;
                    }
                }
                else if (parsed.event === 'token') {
                    if (!firstTokenReceived) {
                        firstTokenReceived = true;
                        thinkingContent.classList.add('finished');
                    }
                    fullResponse += parsed.data;
                    responseContainer.innerHTML = marked.parse(fullResponse);
                    chatThread.scrollTop = chatThread.scrollHeight;
                }
                else if (parsed.event === 'done') {
                    updateAgentStatus('Complete', 'done');
                    
                    // Apply heavy syntax highlighting and copy buttons only ONCE when complete
                    responseContainer.querySelectorAll('pre code').forEach((block) => {
                        hljs.highlightElement(block);
                    });
                    addCopyButtons(responseContainer);
                    
                    if (parsed.data.sources && parsed.data.sources.length > 0) {
                        let sourcesHtml = `<div class="sources-container"><div class="sources-title">Sources</div><div class="sources-list">`;
                        parsed.data.sources.forEach(s => {
                            let domain = s;
                            try {
                                const url = new URL(s);
                                domain = url.hostname;
                            } catch(e) {}
                            
                            sourcesHtml += `
                                <a href="${s}" target="_blank" class="source-card" title="${s}">
                                    <div class="source-icon"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"></path><polyline points="16 3 21 3 21 8"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg></div>
                                    <div class="source-details">
                                        <div class="source-domain">${domain}</div>
                                    </div>
                                </a>`;
                        });
                        sourcesHtml += `</div></div>`;
                        if (messageExtras) messageExtras.innerHTML += sourcesHtml;
                    }
                    
                    if (parsed.data.context) {
                        let contextHtml = `
                            <div class="rag-context-block" style="margin-top: 20px; padding: 16px; border-left: 2px solid rgba(255,255,255,0.1); color: var(--color-text-muted); font-size: 0.85rem; max-height: 200px; overflow-y: auto;">
                                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">
                                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                                    Extracted Context
                                </div>
                                <div style="white-space: pre-wrap; font-family: var(--font-mono); opacity: 0.8;">${parsed.data.context}</div>
                            </div>
                        `;
                        if (messageExtras) messageExtras.innerHTML += contextHtml;
                    }
                    
                    chatThread.scrollTop = chatThread.scrollHeight;
                    
                    // Attach full content to copy button
                    msgDiv.querySelector('.copy-msg-btn').onclick = () => {
                        navigator.clipboard.writeText(fullResponse);
                        const btn = msgDiv.querySelector('.copy-msg-btn');
                        btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#00e676" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg> Copied!';
                        setTimeout(() => {
                            btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Copy';
                        }, 2000);
                    };
                    messageActions.style.display = 'flex';
                    
                    if (activeEventSource) activeEventSource.close();
                    activeEventSource = null;
                    sendBtn.style.display = 'flex';
                    stopBtn.style.display = 'none';
                    loadSessions();
                }
                else if (parsed.event === 'error') {
                    updateAgentStatus('Error encountered', 'error');
                    responseContainer.innerHTML += `<br><br><span style="color:var(--color-error)">Exception: ${parsed.data}</span>`;
                    messageActions.style.display = 'flex';
                    if (activeEventSource) activeEventSource.close();
                    activeEventSource = null;
                    sendBtn.style.display = 'flex';
                    stopBtn.style.display = 'none';
                }
            } catch (err) {
                console.error("Error parsing SSE", err);
            }
        };
        
        activeEventSource.onerror = (e) => {
            console.error("EventSource failed", e);
            if (activeEventSource) activeEventSource.close();
            activeEventSource = null;
            updateAgentStatus('Connection lost', 'error');
            sendBtn.style.display = 'flex';
            stopBtn.style.display = 'none';
            messageActions.style.display = 'flex';
        };
        
    } catch (err) {
        console.error(err);
        responseContainer.innerHTML = `<span style="color:var(--color-error)">System Failure: ${err.message}</span>`;
        updateAgentStatus('Failed to send query', 'error');
        sendBtn.style.display = 'flex';
        stopBtn.style.display = 'none';
    }
}

sendBtn.addEventListener('click', handlePromptSubmit);

promptInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handlePromptSubmit(e);
    }
});