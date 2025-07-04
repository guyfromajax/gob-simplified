export function easeInOutQuad(t) {
  return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

export class AnimationEngine {
  constructor(ctx, gridToPixels, drawPlayer, speedMultiplier = 1.0) {
    this.ctx = ctx;
    this.gridToPixels = gridToPixels;
    this.drawPlayer = drawPlayer;
    this.speedMultiplier = speedMultiplier;
    this.turnIndex = 0;
    this.turns = [];
    this.activePlayers = [];
    this.startTime = 0;
    this.currentPositions = {}; // playerId -> {x, y}
  }
  

  setTeams(teamInfo, players) {
    this.teamInfo = teamInfo;
    this.players = players;
  }

  start(turns) {
    this.turnIndex = 0;
    this.turns = turns;
    this.playNextTurn();
  }

  playNextTurn() {
    if (this.turnIndex >= this.turns.length) {
      return;
    }
    const turn = this.turns[this.turnIndex];
    this.activePlayers = turn.animations || [];
    this.startTime = performance.now();

    requestAnimationFrame(this.animateFrame.bind(this));
  }

  animateFrame(currentTime) {
    const elapsed = (currentTime - this.startTime) * this.speedMultiplier;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

    const maxDuration = Math.max(
      ...this.activePlayers.map(p => p.movement?.at(-1)?.timestamp || 0)
    );

    this.activePlayers.forEach(p => {
      const movement = p.movement || [];
      if (movement.length === 0) return;
      let i = 0;
      while (i < movement.length - 1 && elapsed >= movement[i + 1].timestamp) {
        i++;
      }
      const a = movement[i];
      const b = movement[i + 1] || a;
      const tRaw = b.timestamp === a.timestamp
        ? 1
        : (elapsed - a.timestamp) / (b.timestamp - a.timestamp);
      const t = Math.min(1, Math.max(0, easeInOutQuad(tRaw)));
      const x = a.coords.x + (b.coords.x - a.coords.x) * t;
      const y = a.coords.y + (b.coords.y - a.coords.y) * t;
      this.currentPositions[p.playerId] = { x, y };
      const pixel = this.gridToPixels(x, y);
      this.drawPlayer({ ...p }, pixel);
    });

    if (elapsed < maxDuration) {
      requestAnimationFrame(this.animateFrame.bind(this));
    } else {
      // ensure final positions are drawn once more
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
      this.activePlayers.forEach(p => {
        const last = p.movement.at(-1);
        const pos = last ? last.coords : this.currentPositions[p.playerId];
        this.currentPositions[p.playerId] = pos;
        this.drawPlayer({ ...p }, this.gridToPixels(pos.x, pos.y));
      });
      this.turnIndex++;
      this.playNextTurn();
    }
  }
}
