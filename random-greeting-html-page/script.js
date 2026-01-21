// Function to calculate and display the countdown to the wedding day
function displayWeddingCountdown() {
    const weddingDate = new Date();
    weddingDate.setDate(weddingDate.getDate() + 20); // Set the wedding date to 20 days from now

    const countdownElement = document.getElementById('greeting');
    if (countdownElement) {
        const now = new Date();
        const timeDifference = weddingDate - now;

        const days = Math.floor(timeDifference / (1000 * 60 * 60 * 24));
        const hours = Math.floor((timeDifference % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((timeDifference % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeDifference % (1000 * 60)) / 1000);

        countdownElement.textContent = `Eshita's wedding is in ${days} days, ${hours} hours, ${minutes} minutes, and ${seconds} seconds!`;
    }
}

// Function to animate flying wishes
function animateFlyingWishes() {
    const wishes = ['Congratulations!', 'Best Wishes!', 'Happy Wedding!', 'Cheers to Love!', 'Forever Together!'];
    const container = document.querySelector('.container');

    wishes.forEach((wish, index) => {
        const wishElement = document.createElement('div');
        wishElement.textContent = wish;
        wishElement.className = 'flying-wish';
        wishElement.style.animationDelay = `${index * 2}s`;
        container.appendChild(wishElement);
    });
}

// Update the countdown every second
setInterval(displayWeddingCountdown, 1000);

// Call the functions on page load
document.addEventListener('DOMContentLoaded', () => {
    displayWeddingCountdown();
    animateFlyingWishes();
});