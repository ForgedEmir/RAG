// Oracle des Archives - JavaScript Interface

const userInput = document.getElementById('userInput');
const revealButton = document.getElementById('revealButton');
const oracleResponses = document.getElementById('oracleResponses');
const loadingIndicator = document.getElementById('loadingIndicator');
const welcomeMessage = document.getElementById('welcomeMessage');

let isFirstMessage = true;

function addUserQuestion(question) {
    // Hide welcome message on first user message
    if (isFirstMessage && welcomeMessage) {
        welcomeMessage.classList.add('fade-out');
        setTimeout(() => {
            if (welcomeMessage.parentNode) {
                welcomeMessage.parentNode.removeChild(welcomeMessage);
            }
        }, 800);
        isFirstMessage = false;
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'oracle-message';
    messageDiv.innerHTML = `
        <div class="user-question">
            ${question}
        </div>
    `;
    oracleResponses.appendChild(messageDiv);
}

function addOracleResponse(response) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'oracle-message';
    messageDiv.innerHTML = `
        <div class="oracle-response">
            ${response}
        </div>
    `;
    oracleResponses.appendChild(messageDiv);
    oracleResponses.scrollTop = oracleResponses.scrollHeight;
}

function showLoading() {
    loadingIndicator.classList.add('visible');
}

function hideLoading() {
    loadingIndicator.classList.remove('visible');
}

// Main function to consult the Oracle
async function consultOracle() {
    const question = userInput.value.trim();
    
    if (!question) {
        alert('Veuillez écrire votre question sur le parchemin mystique...');
        return;
    }

    addUserQuestion(question);
    userInput.value = '';
    showLoading();
    
    try {
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: question })
        });

        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const data = await response.json();
        hideLoading();
        
        // Display response with mystical delay
        setTimeout(() => {
            addOracleResponse(data.response);
        }, 500);
        
    } catch (error) {
        console.error('Erreur:', error);
        hideLoading();
        
        setTimeout(() => {
            addOracleResponse(
                'Les brumes mystiques obscurcissent ma vision... L\'Oracle semble être dans un sommeil profond. ' +
                'Vérifiez que le serveur des mystères soit éveillé (http://localhost:8000) et tentez à nouveau votre invocation.'
            );
        }, 500);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Event listeners
    revealButton.addEventListener('click', consultOracle);

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            consultOracle();
        }
    });

    userInput.focus();

    // Suppression des gestionnaires d'événements qui modifient le style de fond
    // userInput.addEventListener('focus', () => {
    //     userInput.style.background = 'rgba(244,228,188,0.1)';
    // });

    // userInput.addEventListener('blur', () => {
    //     userInput.style.background = 'transparent';
    // });
});