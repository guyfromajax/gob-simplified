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
    this.currentPositions = {};
    this.ballCoords = null;
    this.ballImage = null;
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
      if (p.hasBall) {
        this.ballCoords = { ...pixel };
      }
      this.drawPlayer({ ...p }, pixel);
    });

    if (elapsed < maxDuration) {
      // Ongoing animation: draw players and set ballCoords
      this.activePlayers.forEach(p => {
        const movement = p.movement || [];
        if (movement.length === 0) return;
        let i = 0;
        while (i < movement.length - 1 && elapsed >= movement[i + 1].timestamp) i++;
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
        if (p.hasBall) this.ballCoords = { ...pixel };
        this.drawPlayer({ ...p }, pixel);
      });

      // ✅ Draw ball after players
      if (this.ballCoords && this.ballImage?.complete) {
        const ballSize = 16;
        ctx.drawImage(
          this.ballImage,
          this.ballCoords.x - ballSize / 2,
          this.ballCoords.y - ballSize / 2,
          ballSize,
          ballSize
        );
      }
      requestAnimationFrame(this.animateFrame.bind(this));
    } else {
      // ensure final positions are drawn once more
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
      this.activePlayers.forEach(p => {
        const last = p.movement.at(-1);
        const pos = last ? last.coords : this.currentPositions[p.playerId];
        this.currentPositions[p.playerId] = pos;
        this.drawPlayer({ ...p }, this.gridToPixels(pos.x, pos.y));
        if (p.hasBall) {
          const pixel = this.gridToPixels(pos.x, pos.y);
          this.ballCoords = { ...pixel };
        }   
        if (this.ballCoords) {
          console.log("Ball coords:", this.ballCoords);
        } else {
          console.log("No ball coords");
        }        
        
      });   
      if (this.ballCoords && this.ballImage?.complete) {
        const ballSize = 16;
        ctx.drawImage(
          this.ballImage,
          this.ballCoords.x - ballSize / 2,
          this.ballCoords.y - ballSize / 2,
          ballSize,
          ballSize
        );
      }
      
      this.turnIndex++;
      this.playNextTurn();
    }
  }

  setBallImage(img) {
    this.ballImage = img;
  } 
}