// Function to display a random greeting message
function displayRandomGreeting() {
    const greetings = [
        'Hello, how are you?',
        'Hi there! How are you doing?',
        'Greetings! How have you been?',
        'Hey! What’s up?',
        'Howdy! How are things going?'
    ];

    // Select a random greeting
    const randomIndex = Math.floor(Math.random() * greetings.length);
    const randomGreeting = greetings[randomIndex];

    // Display the greeting in the element with id 'greeting'
    const greetingElement = document.getElementById('greeting');
    if (greetingElement) {
        greetingElement.textContent = randomGreeting;
    }
}

// Call the function on page load
document.addEventListener('DOMContentLoaded', displayRandomGreeting);