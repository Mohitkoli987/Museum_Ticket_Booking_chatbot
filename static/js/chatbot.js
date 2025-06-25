// chatbot.js
document.addEventListener('DOMContentLoaded', function() {
    const chatbotBody = document.getElementById('chatbot-body');
    const toggleChatbotButton = document.getElementById('toggleChatbot');

    // Initialize chatbot interaction
    startChat();

    toggleChatbotButton.addEventListener('click', function() {
        const chatbotContainer = document.querySelector('.chatbot-container');
        if (chatbotContainer.style.display === 'none') {
            chatbotContainer.style.display = 'block';
            toggleChatbotButton.textContent = 'Close Chat';
        } else {
            chatbotContainer.style.display = 'none';
            toggleChatbotButton.textContent = 'Open Chat';
        }
    });

    function startChat() {
        sendMessageToChatbot('book');
    }

    function sendMessageToChatbot(message) {
        fetch('/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            appendMessage('Bot', data.message);
        });
    }

    function appendMessage(sender, message) {
        const messageElement = document.createElement('p');
        messageElement.textContent = `${sender}: ${message}`;
        chatbotBody.appendChild(messageElement);
        chatbotBody.scrollTop = chatbotBody.scrollHeight;
    }

    chatbotBody.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            const inputField = document.querySelector('#chatbot-input');
            const userMessage = inputField.value;
            appendMessage('You', userMessage);
            sendMessageToChatbot(userMessage);
            inputField.value = '';
        }
    });
});
