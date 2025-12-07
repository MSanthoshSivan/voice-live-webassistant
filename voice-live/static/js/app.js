// Socket.IO Connection
const socket = io();

// State
let isAssistantRunning = false;
let conversationHistory = [];
let functionCallCount = 0;
let messageCount = 0;

// DOM Elements
const startBtn = document.getElementById('start-btn');
const connectionStatus = document.getElementById('connection-status');
const sessionIdEl = document.getElementById('session-id');
const lastActivityEl = document.getElementById('last-activity');
const messageCountEl = document.getElementById('message-count');
const conversationContainer = document.getElementById('conversation-container');
const functionContainer = document.getElementById('function-container');
const toolsContainer = document.getElementById('tools-container');
const audioStatusEl = document.getElementById('audio-status');
const speakingIndicator = document.getElementById('speaking-indicator');
const inputMeter = document.getElementById('input-meter');
const outputMeter = document.getElementById('output-meter');
const functionCountEl = document.getElementById('function-count');
const clearConversationBtn = document.getElementById('clear-conversation');

// Utility Functions
function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function updateLastActivity() {
    const now = new Date();
    lastActivityEl.textContent = now.toLocaleTimeString('en-US');
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<div class="toast-message">${message}</div>`;
    
    const container = document.getElementById('toast-container');
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function clearWelcomeMessage() {
    const welcomeMsg = conversationContainer.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }
}

function addUserMessage(text, timestamp) {
    clearWelcomeMessage();
    
    const messageEl = document.createElement('div');
    messageEl.className = 'message user';
    messageEl.innerHTML = `
        <div class="message-header">
            <span class="message-sender">👤 You</span>
            <span class="message-time">${formatTime(timestamp)}</span>
        </div>
        <div class="message-content">${escapeHtml(text)}</div>
    `;
    
    conversationContainer.appendChild(messageEl);
    conversationContainer.scrollTop = conversationContainer.scrollHeight;
    
    messageCount++;
    messageCountEl.textContent = messageCount;
    updateLastActivity();
}

function addAssistantMessage(text, timestamp) {
    clearWelcomeMessage();
    
    const messageEl = document.createElement('div');
    messageEl.className = 'message assistant';
    messageEl.innerHTML = `
        <div class="message-header">
            <span class="message-sender">🤖 Assistant</span>
            <span class="message-time">${formatTime(timestamp)}</span>
        </div>
        <div class="message-content">${escapeHtml(text)}</div>
    `;
    
    conversationContainer.appendChild(messageEl);
    conversationContainer.scrollTop = conversationContainer.scrollHeight;
    
    messageCount++;
    messageCountEl.textContent = messageCount;
    updateLastActivity();
}

function updateAssistantMessage(text) {
    const messages = conversationContainer.querySelectorAll('.message.assistant');
    if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1];
        const contentEl = lastMessage.querySelector('.message-content');
        contentEl.textContent = text;
    }
}

function addFunctionCall(functionName, args, result, timestamp) {
    // Clear empty state
    const emptyState = functionContainer.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }
    
    const functionEl = document.createElement('div');
    functionEl.className = 'function-call';
    
    let argsHtml = '';
    let resultHtml = '';
    
    if (args) {
        try {
            const argsObj = typeof args === 'string' ? JSON.parse(args) : args;
            argsHtml = `
                <div class="function-args">
                    <strong>Arguments:</strong>
                    <code>${JSON.stringify(argsObj, null, 2)}</code>
                </div>
            `;
        } catch (e) {
            argsHtml = `
                <div class="function-args">
                    <strong>Arguments:</strong>
                    <code>${escapeHtml(args)}</code>
                </div>
            `;
        }
    }
    
    if (result) {
        try {
            const resultObj = typeof result === 'string' ? JSON.parse(result) : result;
            resultHtml = `
                <div class="function-result">
                    <strong>Result:</strong>
                    <code>${JSON.stringify(resultObj, null, 2)}</code>
                </div>
            `;
        } catch (e) {
            resultHtml = `
                <div class="function-result">
                    <strong>Result:</strong>
                    <code>${escapeHtml(JSON.stringify(result))}</code>
                </div>
            `;
        }
    }
    
    functionEl.innerHTML = `
        <div class="function-header">
            <span class="function-name">⚙️ ${escapeHtml(functionName)}</span>
            <span class="function-time">${formatTime(timestamp)}</span>
        </div>
        ${argsHtml}
        ${resultHtml}
    `;
    
    functionContainer.appendChild(functionEl);
    functionContainer.scrollTop = functionContainer.scrollHeight;
    
    functionCallCount++;
    functionCountEl.textContent = functionCallCount;
    updateLastActivity();
}

function displayTools(tools) {
    toolsContainer.innerHTML = '';
    
    if (!tools || tools.length === 0) {
        toolsContainer.innerHTML = '<p class="empty-state">No tools available</p>';
        return;
    }
    
    tools.forEach(tool => {
        const toolEl = document.createElement('div');
        toolEl.className = 'tool-item';
        toolEl.innerHTML = `
            <div class="tool-name">🔧 ${escapeHtml(tool.name)}</div>
            <div class="tool-description">${escapeHtml(tool.description)}</div>
        `;
        toolsContainer.appendChild(toolEl);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateAudioLevel(level, type) {
    const meter = type === 'input' ? inputMeter : outputMeter;
    const percentage = Math.min(level * 100, 100);
    meter.style.width = `${percentage}%`;
    
    // Fade out if no activity
    setTimeout(() => {
        if (meter.style.width === `${percentage}%`) {
            meter.style.width = '0%';
        }
    }, 200);
}

// Event Handlers
startBtn.addEventListener('click', () => {
    if (!isAssistantRunning) {
        socket.emit('start_assistant');
        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';
    } else {
        // Stop assistant
        socket.emit('stop_assistant');
        startBtn.disabled = true;
        startBtn.textContent = 'Stopping...';
    }
});

clearConversationBtn.addEventListener('click', () => {
    conversationContainer.innerHTML = `
        <div class="welcome-message">
            <h3>Conversation Cleared 🗑️</h3>
            <p>Continue speaking to start a new conversation.</p>
        </div>
    `;
    messageCount = 0;
    messageCountEl.textContent = '0';
});

// Socket Events
socket.on('connect', () => {
    console.log('Connected to server');
    // Don't change status badge - it shows assistant status, not socket status
    updateLastActivity();
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    connectionStatus.textContent = 'Server Offline';
    connectionStatus.className = 'status-badge disconnected';
    isAssistantRunning = false;
    startBtn.disabled = true;
    startBtn.textContent = 'Server Offline';
    startBtn.classList.remove('btn-stop');
});

socket.on('status', (data) => {
    console.log('Status:', data);
    showToast(data.message, 'info');
    
    if (data.status === 'connecting') {
        connectionStatus.textContent = 'Starting...';
        connectionStatus.className = 'status-badge connecting';
    } else if (data.status === 'ready') {
        connectionStatus.textContent = 'Running';
        connectionStatus.className = 'status-badge connected';
        isAssistantRunning = true;
        startBtn.disabled = false;
        startBtn.textContent = 'Stop Assistant';
        startBtn.classList.add('btn-stop');
        audioStatusEl.textContent = 'Active';
        showToast('🎤 Voice assistant is ready! Start speaking...', 'success');
    }
    updateLastActivity();
});

socket.on('assistant_started', (data) => {
    console.log('Assistant started:', data);
    showToast(data.message, 'success');
});

socket.on('session_ready', (data) => {
    console.log('Session ready:', data);
    sessionIdEl.textContent = data.session_id.substring(0, 16) + '...';
    updateLastActivity();
});

socket.on('tools_configured', (data) => {
    console.log('Tools configured:', data);
    displayTools(data.tools);
});

socket.on('user_speaking', (data) => {
    if (data.speaking) {
        speakingIndicator.classList.add('active');
        audioStatusEl.textContent = 'Listening...';
    } else {
        speakingIndicator.classList.remove('active');
        audioStatusEl.textContent = 'Processing...';
    }
    updateLastActivity();
});

socket.on('user_transcript', (data) => {
    console.log('User transcript:', data);
    addUserMessage(data.text, data.timestamp);
});

socket.on('response_started', (data) => {
    console.log('Response started:', data);
    audioStatusEl.textContent = 'Speaking...';
    // Reset audio transcript accumulator for new response
    currentAudioTranscript = '';
});

// Track accumulated audio transcript
let currentAudioTranscript = '';

socket.on('response_audio_transcript_delta', (data) => {
    console.log('Audio transcript delta:', data);
    // Accumulate the audio transcript
    currentAudioTranscript += data.delta;
    
    // Find the last assistant message in the conversation
    const messages = conversationContainer.querySelectorAll('.message.assistant');
    const lastUserMessage = conversationContainer.querySelector('.message.user:last-of-type');
    
    // Find the last assistant message that comes after the last user message
    let lastAssistantMessage = null;
    if (lastUserMessage) {
        let next = lastUserMessage.nextElementSibling;
        while (next) {
            if (next.classList.contains('message') && next.classList.contains('assistant')) {
                lastAssistantMessage = next;
                break;
            }
            next = next.nextElementSibling;
        }
    } else if (messages.length > 0) {
        // If no user message yet, use the last assistant message
        lastAssistantMessage = messages[messages.length - 1];
    }
    
    if (lastAssistantMessage) {
        // Update existing message - just update the content, don't increment counter
        const contentEl = lastAssistantMessage.querySelector('.message-content');
        contentEl.textContent = currentAudioTranscript;
    } else {
        // Create new message only if it doesn't exist
        clearWelcomeMessage();
        const messageEl = document.createElement('div');
        messageEl.className = 'message assistant';
        messageEl.innerHTML = `
            <div class="message-header">
                <span class="message-sender">🤖 Assistant</span>
                <span class="message-time">${formatTime(new Date().toISOString())}</span>
            </div>
            <div class="message-content">${escapeHtml(currentAudioTranscript)}</div>
        `;
        conversationContainer.appendChild(messageEl);
        messageCount++;
        messageCountEl.textContent = messageCount;
    }
    conversationContainer.scrollTop = conversationContainer.scrollHeight;
    updateLastActivity();
});

socket.on('response_delta', (data) => {
    // Update or create assistant message with accumulated text
    const messages = conversationContainer.querySelectorAll('.message.assistant');
    const lastUserMessage = conversationContainer.querySelector('.message.user:last-of-type');
    
    // Find the last assistant message that comes after the last user message
    let lastAssistantMessage = null;
    if (lastUserMessage) {
        let next = lastUserMessage.nextElementSibling;
        while (next) {
            if (next.classList.contains('message') && next.classList.contains('assistant')) {
                lastAssistantMessage = next;
                break;
            }
            next = next.nextElementSibling;
        }
    }
    
    if (lastAssistantMessage) {
        // Update existing message
        const contentEl = lastAssistantMessage.querySelector('.message-content');
        contentEl.textContent = data.full_text;
    } else {
        // Create new message if it doesn't exist
        clearWelcomeMessage();
        const messageEl = document.createElement('div');
        messageEl.className = 'message assistant';
        messageEl.innerHTML = `
            <div class="message-header">
                <span class="message-sender">🤖 Assistant</span>
                <span class="message-time">${formatTime(new Date().toISOString())}</span>
            </div>
            <div class="message-content">${escapeHtml(data.full_text)}</div>
        `;
        conversationContainer.appendChild(messageEl);
        messageCount++;
        messageCountEl.textContent = messageCount;
    }
    conversationContainer.scrollTop = conversationContainer.scrollHeight;
    updateLastActivity();
});

socket.on('conversation_item', (data) => {
    console.log('Conversation item:', data);
    // This event contains the complete user/assistant exchange
    // Make sure assistant message is displayed if not already
    if (data.assistant && data.assistant.trim()) {
        // Check if we already have this message
        const messages = conversationContainer.querySelectorAll('.message.assistant');
        let foundMatch = false;
        
        messages.forEach(msg => {
            const content = msg.querySelector('.message-content');
            if (content && content.textContent === data.assistant) {
                foundMatch = true;
            }
        });
        
        // If not found, add it
        if (!foundMatch) {
            addAssistantMessage(data.assistant, data.timestamp);
        }
    }
    updateLastActivity();
});

socket.on('assistant_stopped', (data) => {
    console.log('Assistant stopped:', data);
    isAssistantRunning = false;
    startBtn.disabled = false;
    startBtn.textContent = 'Start Assistant';
    startBtn.classList.remove('btn-stop');
    connectionStatus.textContent = 'Not Running';
    connectionStatus.className = 'status-badge disconnected';
    audioStatusEl.textContent = 'Idle';
    showToast('Assistant stopped', 'info');
    updateLastActivity();
});

socket.on('assistant_finished_speaking', () => {
    console.log('Assistant finished speaking');
    audioStatusEl.textContent = 'Ready';
    updateLastActivity();
});

socket.on('audio_level', (data) => {
    updateAudioLevel(data.level, data.type);
});

socket.on('audio_status', (data) => {
    console.log('Audio status:', data);
    if (data.status === 'capturing') {
        audioStatusEl.textContent = 'Recording';
    } else if (data.status === 'playing') {
        audioStatusEl.textContent = 'Ready';
    } else if (data.status === 'stopped') {
        audioStatusEl.textContent = 'Idle';
    }
});

socket.on('function_call_started', (data) => {
    console.log('Function call started:', data);
    showToast(`⚙️ Calling function: ${data.function}`, 'warning');
    // We'll add the full function call when we get the result
    currentFunctionCalls[data.call_id] = {
        function: data.function,
        timestamp: data.timestamp
    };
});

// Track ongoing function calls
const currentFunctionCalls = {};

socket.on('function_arguments', (data) => {
    console.log('Function arguments:', data);
    if (currentFunctionCalls[data.call_id]) {
        currentFunctionCalls[data.call_id].arguments = data.arguments;
    }
});

socket.on('function_result', (data) => {
    console.log('Function result:', data);
    const callInfo = currentFunctionCalls[data.call_id];
    if (callInfo) {
        addFunctionCall(
            data.function,
            callInfo.arguments || data.arguments,
            data.result,
            data.timestamp
        );
        delete currentFunctionCalls[data.call_id];
    } else {
        // Fallback if we don't have the call info
        addFunctionCall(data.function, null, data.result, data.timestamp);
    }
});

socket.on('function_error', (data) => {
    console.error('Function error:', data);
    showToast(`❌ Function error: ${data.error}`, 'error');
});

socket.on('error', (data) => {
    console.error('Error:', data);
    showToast(`❌ Error: ${data.message}`, 'error');
    isAssistantRunning = false;
    startBtn.disabled = false;
    startBtn.textContent = 'Start Assistant';
    startBtn.classList.remove('btn-stop');
    connectionStatus.textContent = 'Error';
    connectionStatus.className = 'status-badge disconnected';
});

// Initialize
console.log('Voice Live Web UI Loaded');

// Check configuration on load
fetch('/api/config')
    .then(response => response.json())
    .then(data => {
        console.log('Configuration:', data);
        if (!data.configured) {
            showToast('⚠️ API key not configured. Please set AZURE_VOICELIVE_API_KEY environment variable.', 'warning');
            startBtn.disabled = true;
            startBtn.textContent = 'Not Configured';
        }
    })
    .catch(error => {
        console.error('Error checking config:', error);
        showToast('⚠️ Error checking configuration', 'error');
    });
