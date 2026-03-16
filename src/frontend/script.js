// Oracle des Archives - JavaScript Interface

// Terms and Conditions Management
const TERMS_ACCEPTED_KEY = 'oracleTermsAccepted';

function checkTermsAcceptance() {
    const accepted = localStorage.getItem(TERMS_ACCEPTED_KEY);
    const termsModal = document.getElementById('termsModal');
    
    if (accepted === 'true') {
        termsModal.style.display = 'none';
    } else {
        termsModal.style.display = 'flex';
    }
}

function initializeTermsModal() {
    const termsModal = document.getElementById('termsModal');
    const acceptCheckbox = document.getElementById('acceptTerms');
    const acceptButton = document.getElementById('acceptTermsButton');
    
    // Enable/disable button based on checkbox
    acceptCheckbox.addEventListener('change', function() {
        acceptButton.disabled = !this.checked;
    });
    
    // Handle accept button click
    acceptButton.addEventListener('click', function() {
        if (acceptCheckbox.checked) {
            localStorage.setItem(TERMS_ACCEPTED_KEY, 'true');
            termsModal.style.display = 'none';
        }
    });
}

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

function addBlockedMessage(message, blockType) {
    const isInjection = blockType === 'prompt_injection';
    const messageDiv = document.createElement('div');
    messageDiv.className = 'oracle-message';
    messageDiv.innerHTML = `
        <div class="oracle-response-blocked ${isInjection ? 'blocked-injection' : 'blocked-offtopic'}">
            ${message}
        </div>
    `;
    oracleResponses.appendChild(messageDiv);
    oracleResponses.scrollTop = oracleResponses.scrollHeight;
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
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question
            })
        });

        if (!response.ok) {
            throw new Error(`Erreur HTTP: ${response.status}`);
        }

        const data = await response.json();
        hideLoading();

        setTimeout(() => {
            if (data.blocked) {
                addBlockedMessage(data.reponse, data.block_type);
            } else {
                addOracleResponse(data.reponse);
            }
        }, 500);

    } catch (error) {
        console.error('Erreur:', error);
        hideLoading();

        setTimeout(() => {
            addOracleResponse(
                'Les brumes mystiques obscurcissent ma vision... L\'Oracle semble être dans un sommeil profond. ' +
                'Vérifiez que le serveur des mystères soit éveillé et tentez à nouveau votre invocation.'
            );
        }, 500);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize terms modal
    checkTermsAcceptance();
    initializeTermsModal();
    
    // Event listeners
    revealButton.addEventListener('click', consultOracle);

    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            consultOracle();
        }
    });

    userInput.focus();

    // userInput.addEventListener('focus', () => {
    //     userInput.style.background = 'rgba(244,228,188,0.1)';
    // });

    // userInput.addEventListener('blur', () => {
    //     userInput.style.background = 'transparent';
    // });
});