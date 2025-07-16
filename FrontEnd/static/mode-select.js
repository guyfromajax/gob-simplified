const scrimmageBtn = document.getElementById('scrimmage-btn');
const tournamentBtn = document.getElementById('tournament-btn');

if (scrimmageBtn) {
  scrimmageBtn.addEventListener('click', () => {
    window.location.href = './index.html';
  });
}

if (tournamentBtn) {
  tournamentBtn.addEventListener('click', () => {
    window.location.href = './tournament-select.html';
  });
}
