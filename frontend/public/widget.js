(function () {
    // Configuration
    let config = {
        twinId: '',
        apiKey: '',
        apiBaseUrl: 'http://localhost:8000',
        title: 'Digital Assistant',
        primaryColor: '#4f46e5',
        greeting: 'Hello! How can I help you today?',
    };

    let sessionId = localStorage.getItem('dt_brain_session_id');

    // Create Styles
    const style = document.createElement('style');
    style.innerHTML = `
        #dt-widget-container {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 10000;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }
        #dt-widget-trigger {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: \${config.primaryColor};
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }
        #dt-widget-trigger:hover {
            transform: scale(1.1);
        }
        #dt-widget-trigger svg {
            width: 30px;
            height: 30px;
            color: white;
        }
        #dt-chat-window {
            position: absolute;
            bottom: 80px;
            right: 0;
            width: 380px;
            height: 600px;
            background: white;
            border-radius: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            display: none;
            flex-direction: column;
            overflow: hidden;
            border: 1px solid rgba(0,0,0,0.05);
            transition: all 0.3s ease;
            transform-origin: bottom right;
        }
        .dt-header {
            padding: 20px;
            background: \${config.primaryColor};
            color: white;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .dt-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #f8fafc;
        }
        .dt-message {
            margin-bottom: 12px;
            max-width: 85%;
            padding: 12px 16px;
            border-radius: 16px;
            font-size: 14px;
            line-height: 1.5;
        }
        .dt-user {
            background: \${config.primaryColor};
            color: white;
            align-self: flex-end;
            margin-left: auto;
            border-bottom-right-radius: 4px;
        }
        .dt-ai {
            background: white;
            color: #1e293b;
            align-self: flex-start;
            border: 1px solid #e2e8f0;
            border-bottom-left-radius: 4px;
        }
        .dt-input-area {
            padding: 16px;
            background: white;
            border-top: 1px solid #e2e8f0;
            display: flex;
            gap: 10px;
        }
        .dt-input {
            flex: 1;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 10px 14px;
            outline: none;
            font-size: 14px;
        }
        .dt-send {
            background: \${config.primaryColor};
            color: white;
            border: none;
            border-radius: 10px;
            padding: 8px 16px;
            cursor: pointer;
            font-weight: bold;
        }
        .dt-loading {
            font-size: 12px;
            color: #64748b;
            margin-bottom: 10px;
            display: none;
        }
    `;
    document.head.appendChild(style);

    // Global Initialization Function
    window.initChatWidget = function (options) {
        config = { ...config, ...options };
        createWidget();
    };

    function createWidget() {
        const container = document.createElement('div');
        container.id = 'dt-widget-container';
        container.innerHTML = `
            <div id="dt-chat-window">
                <div class="dt-header">
                    <span style="font-weight: 800; font-size: 18px;">\${config.title}</span>
                    <button id="dt-close" style="background:none; border:none; color:white; cursor:pointer; font-size:20px;">×</button>
                </div>
                <div class="dt-messages" id="dt-msg-list">
                    <div class="dt-message dt-ai">\${config.greeting}</div>
                </div>
                <div id="dt-loader" class="dt-loading" style="padding-left: 20px;">Thinking...</div>
                <div class="dt-input-area">
                    <input type="text" id="dt-input" class="dt-input" placeholder="Type a message...">
                    <button id="dt-send" class="dt-send">Send</button>
                </div>
            </div>
            <div id="dt-widget-trigger">
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>
            </div>
        `;
        document.body.appendChild(container);

        const trigger = document.getElementById('dt-widget-trigger');
        const windowEl = document.getElementById('dt-chat-window');
        const closeBtn = document.getElementById('dt-close');
        const sendBtn = document.getElementById('dt-send');
        const input = document.getElementById('dt-input');
        const msgList = document.getElementById('dt-msg-list');
        const loader = document.getElementById('dt-loader');

        trigger.onclick = () => {
            windowEl.style.display = windowEl.style.display === 'flex' ? 'none' : 'flex';
        };

        closeBtn.onclick = () => {
            windowEl.style.display = 'none';
        };

        async function sendMessage() {
            const query = input.value.trim();
            if (!query) return;

            input.value = '';
            appendMessage('user', query);
            loader.style.display = 'block';

            try {
                const response = await fetch(`\${config.apiBaseUrl}/chat-widget/\${config.twinId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query,
                        session_id: sessionId,
                        api_key: config.apiKey
                    })
                });

                if (!response.ok) throw new Error('API request failed');

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let aiMsgEl = appendMessage('ai', '');
                let fullContent = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\n');

                    for (const line of lines) {
                        if (!line.trim()) continue;
                        try {
                            const data = JSON.parse(line);
                            if (data.session_id) {
                                sessionId = data.session_id;
                                localStorage.setItem('dt_brain_session_id', sessionId);
                            }
                            if (data.type === 'content') {
                                fullContent += data.content;
                                aiMsgEl.innerText = fullContent;
                                msgList.scrollTop = msgList.scrollHeight;
                            }
                        } catch (e) {
                            console.error('Error parsing stream chunk', e);
                        }
                    }
                }
            } catch (err) {
                appendMessage('ai', 'Sorry, I encountered an error. Please check the console for details.');
                console.error(err);
            } finally {
                loader.style.display = 'none';
            }
        }

        sendBtn.onclick = sendMessage;
        input.onkeypress = (e) => e.key === 'Enter' && sendMessage();

        function appendMessage(role, text) {
            const div = document.createElement('div');
            div.className = \`dt-message dt-\${role}\`;
            div.innerText = text;
            msgList.appendChild(div);
            msgList.scrollTop = msgList.scrollHeight;
            return div;
        }
    }
})();
