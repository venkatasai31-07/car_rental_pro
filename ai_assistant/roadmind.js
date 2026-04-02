/**
 * ══════════════════════════════════════════════════════════════════════════
 *   ROADMIND AI ASSISTANT — FRONTEND WIDGET
 *   File: ai_assistant/roadmind.js
 *
 *   PLACE THIS FILE AT: your_project/ai_assistant/roadmind.js
 *
 *   ADD TO EVERY HTML PAGE'S <head> TAG:
 *       <link rel="stylesheet" href="../ai_assistant/roadmind.css">
 *       <script src="../ai_assistant/roadmind.js" defer></script>
 *
 *   IMPORTANT: Change BACKEND_URL below to match your Flask server port/address.
 * ══════════════════════════════════════════════════════════════════════════
 */

(function initRoadMindWidget() {

    // ── CHANGE THIS to your backend URL if different ──────────────────────
    const BACKEND_URL = "/api";

    // ── HTML template for the widget ─────────────────────────────────────
    const widgetHTML = `
        <div id="roadmind-widget-container">
            <div id="roadmind-chat-window">
                <div class="roadmind-header">
                    <div class="roadmind-title">
                        <div class="roadmind-avatar">R</div>
                        <div class="roadmind-info">
                            <span class="roadmind-name">RoadMind AI</span>
                            <span class="roadmind-status">Online</span>
                        </div>
                    </div>
                    <button class="roadmind-close" id="roadmind-close-btn" aria-label="Close Chat">
                        <svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                    </button>
                </div>

                <div class="roadmind-messages" id="roadmind-messages">
                    <div class="message-wrapper ai">
                        <div class="message-bubble">
                            Hey there! 👋 I'm RoadMind, your CarRentalPro assistant. How can I help you today?
                        </div>
                    </div>
                </div>

                <div class="roadmind-input-area">
                    <div class="roadmind-input-wrapper">
                        <input type="text" id="roadmind-input" placeholder="Ask about cars, policies, or your bookings..." autocomplete="off">
                    </div>
                    <button id="roadmind-send" disabled aria-label="Send Message">
                        <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                    </button>
                </div>
            </div>

            <!-- Floating Action Button -->
            <div id="roadmind-fab">
                <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/></svg>
            </div>
        </div>
    `;

    // ── Inject only once ─────────────────────────────────────────────────
    if (!document.getElementById('roadmind-widget-container')) {
        document.body.insertAdjacentHTML('beforeend', widgetHTML);
    }

    // ── Element references ────────────────────────────────────────────────
    const fab              = document.getElementById('roadmind-fab');
    const chatWindow       = document.getElementById('roadmind-chat-window');
    const closeBtn         = document.getElementById('roadmind-close-btn');
    const inputField       = document.getElementById('roadmind-input');
    const sendBtn          = document.getElementById('roadmind-send');
    const messagesContainer = document.getElementById('roadmind-messages');

    // ── Helper: Get user details from localStorage ────────────────────────
    function getUserDetails() {
        let email = null, role = 'guest', name = 'there';
        try {
            const userStr = localStorage.getItem('car_rental_user');
            if (userStr) {
                const user = JSON.parse(userStr);
                email = user.email || null;
                role = user.role || 'guest';
                name = user.first_name || 'there';
            }
            
            // Check identity change to flush chat on login/logout
            const currentEmailStr = email || 'guest';
            const lastEmailStr = sessionStorage.getItem('roadmind_email');
            
            if (lastEmailStr && lastEmailStr !== currentEmailStr) {
                sessionStorage.removeItem('roadmind_history');
                sessionStorage.removeItem('roadmind_session');
            }
            sessionStorage.setItem('roadmind_email', currentEmailStr);
            
        } catch(e) {}
        return { email, role, userName: name };
    }

    // Initialize user state FIRST to check for identity resets
    const currentUserInfo = getUserDetails();

    // ── State ─────────────────────────────────────────────────────────────
    let isWidgetOpen = false;
    let sessionId    = sessionStorage.getItem('roadmind_session') || null;
    let chatHistory  = JSON.parse(sessionStorage.getItem('roadmind_history') || '[]');


    // ── Toggle chat open/close ────────────────────────────────────────────
    function toggleChat() {
        isWidgetOpen = !isWidgetOpen;
        if (isWidgetOpen) {
            chatWindow.classList.add('active');
            inputField.focus();
            scrollToBottom();
        } else {
            chatWindow.classList.remove('active');
        }
    }

    if (fab)      fab.addEventListener('click', toggleChat);
    if (closeBtn) closeBtn.addEventListener('click', toggleChat);

    // ── Input handling ────────────────────────────────────────────────────
    if (inputField) {
        inputField.addEventListener('input', () => {
            sendBtn.disabled = inputField.value.trim().length === 0;
        });
        inputField.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    if (sendBtn) sendBtn.addEventListener('click', sendMessage);

    // ── Helpers ───────────────────────────────────────────────────────────
    function scrollToBottom() {
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    function addMessage(text, sender) {
        if (!messagesContainer) return;
        const msgWrapper = document.createElement('div');
        msgWrapper.className = `message-wrapper ${sender}`;

        const msgBubble = document.createElement('div');
        msgBubble.className = 'message-bubble';
        msgBubble.innerHTML = formatResponse(text);

        msgWrapper.appendChild(msgBubble);
        messagesContainer.appendChild(msgWrapper);
        scrollToBottom();

        chatHistory.push({ role: sender, content: text });
        sessionStorage.setItem('roadmind_history', JSON.stringify(chatHistory));
    }

    function showTyping() {
        if (!messagesContainer) return;
        const wrapper = document.createElement('div');
        wrapper.className = 'message-wrapper ai typing';
        wrapper.id = 'roadmind-typing';
        wrapper.innerHTML = `
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        messagesContainer.appendChild(wrapper);
        scrollToBottom();
    }

    function hideTyping() {
        const typingEl = document.getElementById('roadmind-typing');
        if (typingEl) typingEl.remove();
    }

    function formatResponse(text) {
        let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\n/g, '<br>');
        return html;
    }

    // ── Main send logic ───────────────────────────────────────────────────
    async function sendMessage() {
        if (!inputField) return;
        const text = inputField.value.trim();
        if (!text) return;

        inputField.value = '';
        if (sendBtn) sendBtn.disabled = true;

        addMessage(text, 'user');
        showTyping();

        const userDetails = getUserDetails();

        try {
            const response = await fetch(`${BACKEND_URL}/ai-chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message:   text,
                    email:     userDetails.email,
                    role:      userDetails.role,
                    userName:  userDetails.userName,
                    sessionId: sessionId,
                    history:   chatHistory
                })
            });

            const data = await response.json();
            hideTyping();

            if (data.success) {
                if (data.sessionId && !sessionId) {
                    sessionId = data.sessionId;
                    sessionStorage.setItem('roadmind_session', sessionId);
                }
                addMessage(data.reply, 'ai');
            } else {
                addMessage("Oops, I lost connection to the server. Try again!", 'ai');
            }
        } catch (error) {
            console.error('RoadMind AI Error:', error);
            hideTyping();
            addMessage("Sorry, I'm having trouble connecting right now. 😔", 'ai');
        }
    }

    // ── Load history on startup ───────────────────────────────────────────
    function loadExistingMessages() {
        if (!messagesContainer) return;
        if (chatHistory.length > 0) {
            messagesContainer.innerHTML = '';
            for (let msg of chatHistory) {
                const msgWrapper = document.createElement('div');
                msgWrapper.className = `message-wrapper ${msg.role === 'ai' || msg.role === 'system' ? 'ai' : 'user'}`;
                
                const msgBubble = document.createElement('div');
                msgBubble.className = 'message-bubble';
                msgBubble.innerHTML = formatResponse(msg.content);
                
                msgWrapper.appendChild(msgBubble);
                messagesContainer.appendChild(msgWrapper);
            }
            scrollToBottom();
        }
    }

    loadExistingMessages();

})();
