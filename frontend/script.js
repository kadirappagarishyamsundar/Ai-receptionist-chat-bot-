const API_URL = 'http://localhost:5000/api';
let userId = 'user_' + Math.random().toString(36).substr(2, 9);

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Display user message
    displayMessage(message, 'user');
    input.value = '';
    
    // Show loading
    document.getElementById('loading').style.display = 'block';
    
    try {
        // Send to backend
        const response = await fetch(`${API_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                message: message
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Display AI response
            displayMessage(data.response, 'ai');
            
            // If appointment was booked, show success
            if (data.appointment_booked) {
                displayMessage('✅ Appointment booked successfully! Check your email for confirmation.', 'ai');
            }
        } else {
            displayMessage('❌ Error: ' + data.error, 'ai');
        }
    } catch (error) {
        console.error('Error:', error);
        displayMessage('❌ Connection error. Please try again.', 'ai');
    }
    
    // Hide loading
    document.getElementById('loading').style.display = 'none';
}

function displayMessage(message, sender) {
    const chatBox = document.getElementById('chatBox');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    messageDiv.innerHTML = `<p>${message}</p>`;
    chatBox.appendChild(messageDiv);
    
    // Auto scroll to bottom
    chatBox.scrollTop = chatBox.scrollHeight;
}

function handleKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

// Test backend connection on load
window.addEventListener('load', async () => {
    try {
        const response = await fetch(`${API_URL}/health`);
        const data = await response.json();
        console.log('✅ Backend connected:', data);
    } catch (error) {
        console.error('❌ Backend connection failed:', error);
        displayMessage('❌ Cannot connect to backend. Make sure Python server is running!', 'ai');
    }
});