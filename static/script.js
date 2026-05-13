class QuizMasterPro {
    constructor() {
        const urlParams = new URLSearchParams(window.location.search);
        this.currentMode = urlParams.get('mode') || 'quiz';

        // 🔹 Store separate messages per mode
        this.modeMessages = {
            revision: [],
            practice: [],
            quiz: [],
            doubt: []
        };

        this.isTyping = false;
        this.isSending = false;

        this.init();
    }

    init() {
        this.bindEvents();
        this.autoResizeTextarea();
    }

    bindEvents() {
        document.querySelectorAll('.mode-card').forEach(card => {
            card.addEventListener('click', () => {
                const mode = card.dataset.mode;
                this.selectMode(mode);
            });
        });

        document.getElementById('back-btn')?.addEventListener('click', () => {
            window.location.href = '/';
        });

        document.getElementById('send-btn').addEventListener('click', () => {
            this.sendMessage();
        });

        const input = document.getElementById('message-input');
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        input.addEventListener('input', () => {
            this.updateSendButton();
        });
    }

    selectMode(mode) {
        this.currentMode = mode;
        this.updateModeDisplay();
        this.initializeChat();  // load history
    }

    updateModeDisplay() {
        const modeBadge = document.getElementById('mode-badge');
        const modeText = document.getElementById('mode-text');

        if (!modeBadge) return;
        modeBadge.className = 'mode-badge';
        modeBadge.classList.add(this.currentMode);

        modeText.textContent = this.currentMode.charAt(0).toUpperCase() + this.currentMode.slice(1);
    }

    initializeChat() {
        const messagesContainer = document.getElementById('messages-container');
        messagesContainer.innerHTML = "";

        // 🔹 Load stored messages for selected mode
        if (this.modeMessages[this.currentMode]) {
            this.modeMessages[this.currentMode].forEach(msg => {
                this.renderMessage(msg);
            });

            if (this.modeMessages[this.currentMode].length === 0) {
                const welcomeMessage = `Hi! You're in <strong>${this.currentMode.charAt(0).toUpperCase() + this.currentMode.slice(1)}</strong> mode. Ask me anything about your studies and I'll help you prepare for your exams!`;
                this.addMessage(welcomeMessage, 'bot');
            }
        }
    }

    addMessage(text, sender) {
        const message = {
            id: Date.now().toString(),
            text: text,
            sender: sender,
            timestamp: new Date()
        };

        // 🔹 Save message only to current mode
        if (this.modeMessages[this.currentMode]) {
            this.modeMessages[this.currentMode].push(message);
        }

        this.renderMessage(message);
        this.scrollToBottom();
    }

    renderMessage(message) {
        const messagesContainer = document.getElementById('messages-container');

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.sender}-message`;
        messageDiv.innerHTML = `
            <div class="message-content">
                <p>${message.text}</p>
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
    }

    showTypingIndicator() {
        if (this.isTyping) return;

        this.isTyping = true;
        const messagesContainer = document.getElementById('messages-container');

        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.className = 'typing-indicator';
        typingDiv.innerHTML = `
            <div class="typing-content">
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
                <span class="typing-text">Thinking...</span>
            </div>
        `;

        messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
    }

    hideTypingIndicator() {
        this.isTyping = false;
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    async sendMessage() {
        const input = document.getElementById('message-input');
        const text = input.value.trim();

        if (!text || this.isSending) return;

        this.isSending = true;
        this.addMessage(text, 'user');
        input.value = '';
        this.updateSendButton();
        this.resetTextareaHeight();

        try {
            await this.simulateBotResponse(text);
        } catch (error) {
            this.addMessage('⚠️ Sorry, something went wrong. Please try again.', 'bot');
        } finally {
            this.isSending = false;
        }
    }

    async simulateBotResponse(userMessage) {
        this.showTypingIndicator();

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: userMessage,
                    mode: this.currentMode
                })
            });

            const data = await response.json();

            this.hideTypingIndicator();
            this.addMessage(data.reply, 'bot');
        } catch (err) {
            this.hideTypingIndicator();
            this.addMessage("⚠️ Error connecting to AI server.", 'bot');
        }
    }

    updateSendButton() {
        const input = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');

        if (input.value.trim() && !this.isSending) {
            sendBtn.disabled = false;
        } else {
            sendBtn.disabled = true;
        }
    }

    autoResizeTextarea() {
        const input = document.getElementById('message-input');

        input.addEventListener('input', () => {
            this.resetTextareaHeight();

            const scrollHeight = input.scrollHeight;
            const maxHeight = 128;

            if (scrollHeight <= maxHeight) {
                input.style.height = scrollHeight + 'px';
            } else {
                input.style.height = maxHeight + 'px';
            }
        });
    }

    resetTextareaHeight() {
        const input = document.getElementById('message-input');
        input.style.height = '60px';
    }

    scrollToBottom() {
        const messagesContainer = document.getElementById('messages-container');
        setTimeout(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }, 100);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new QuizMasterPro();
});
