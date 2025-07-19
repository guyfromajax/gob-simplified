const scrimmageBtn = document.getElementById('scrimmage-btn');
const tournamentBtn = document.getElementById('tournament-btn');
const franchiseBtn = document.getElementById('franchise-btn');

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

if (franchiseBtn) {
  // franchiseBtn.addEventListener('click', () => {
  //   window.location.href = './franchise-select-team.html';
  // });
  franchiseBtn.addEventListener('click', () => {
    window.location.href = '/franchise/start';
  });
  
}
