document.addEventListener('DOMContentLoaded', function() {
    const dateInput = document.querySelector('input[type="date"]');
    const countdownDisplay = document.querySelector('.countdown');

    dateInput.addEventListener('change', function() {
        const weddingDate = new Date(this.value);
        updateCountdown(weddingDate);
    });

    function updateCountdown(weddingDate) {
        const now = new Date();
        const timeDifference = weddingDate - now;

        if (timeDifference <= 0) {
            countdownDisplay.textContent = 'The wedding day has arrived!';
            return;
        }

        const days = Math.floor(timeDifference / (1000 * 60 * 60 * 24));
        const hours = Math.floor((timeDifference % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((timeDifference % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((timeDifference % (1000 * 60)) / 1000);

        countdownDisplay.textContent = `${days}d ${hours}h ${minutes}m ${seconds}s`;
    }

    setInterval(function() {
        const weddingDate = new Date(dateInput.value);
        if (dateInput.value) {
            updateCountdown(weddingDate);
        }
    }, 1000);
});