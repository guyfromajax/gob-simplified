export function easeInOutQuad(t) {
  return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

function getStepIndexForElapsed(movement, elapsed) {
  if (!movement || movement.length === 0) return 0;
  let i = 0;
  while (i < movement.length - 1 && elapsed >= movement[i + 1].timestamp) i++;
  return i;
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
    const turn = this.turns[this.turnIndex];
    const ctx = this.ctx;
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);

    const maxDuration = Math.max(
      ...this.activePlayers.map(p => p.movement?.at(-1)?.timestamp || 0)
    );

    this.activePlayers.forEach(p => {
      const movement = p.movement || [];
      if (movement.length === 0) return;
      const i = getStepIndexForElapsed(p.movement, elapsed);
      const a = movement[i];
      if (!movement || movement.length === 0) {
        console.warn("⚠️ #1 No movement for", p.playerId, p.pos);
        return;
      }
      
      const b = movement[i + 1] || a;
      const tRaw = b.timestamp === a.timestamp
        ? 1
        : (elapsed - a.timestamp) / (b.timestamp - a.timestamp);
      const t = Math.min(1, Math.max(0, easeInOutQuad(tRaw)));
      const x = a.coords.x + (b.coords.x - a.coords.x) * t;
      const y = a.coords.y + (b.coords.y - a.coords.y) * t;
      this.currentPositions[p.playerId] = { x, y };
      const pixel = this.gridToPixels(x, y);

      const ballTrackEnd = turn.ballTrack?.movement?.[1]?.timestamp;
      const isBallInFlight = !!ballTrackEnd && elapsed < ballTrackEnd;

      console.log(`isBallInFlight: ${isBallInFlight}, elapsed: ${elapsed}, threshold: ${ballTrackEnd}`);


      if (p.hasBallAtStep?.[i] && !isBallInFlight) {
        this.ballCoords = { ...pixel };
        console.log("🎯 Ball attached to", p.pos, p.jersey, "at step", i, this.ballCoords);
      }
      
      this.drawPlayer({ ...p }, pixel);
    });

    if (elapsed < maxDuration) {
      // Ongoing animation: draw players and set ballCoords
      this.activePlayers.forEach(p => { // #2 instance
        const movement = p.movement || [];
        if (movement.length === 0) return;
        const i = getStepIndexForElapsed(p.movement, elapsed);
        const a = movement[i];
        if (!movement || movement.length === 0) {
          console.warn("⚠️ #2 No movement for", p.playerId, p.pos);
          return;
        }
        
        const b = movement[i + 1] || a;
        const tRaw = b.timestamp === a.timestamp
          ? 1
          : (elapsed - a.timestamp) / (b.timestamp - a.timestamp);
        const t = Math.min(1, Math.max(0, easeInOutQuad(tRaw)));
        const x = a.coords.x + (b.coords.x - a.coords.x) * t;
        const y = a.coords.y + (b.coords.y - a.coords.y) * t;
        this.currentPositions[p.playerId] = { x, y };
        const pixel = this.gridToPixels(x, y);
        const isBallInFlight = !!turn.ballTrack && elapsed < turn.ballTrack.movement?.[1]?.timestamp;
        console.log(`isBallInFlight: ${isBallInFlight}, elapsed: ${elapsed}, threshold: ${turn.ballTrack.movement[1]?.timestamp}`);
        if (p.hasBallAtStep?.[i] && !isBallInFlight) {
          this.ballCoords = { ...pixel };
          console.log("🎯 Ball attached to", p.pos, p.jersey, "at step", i, this.ballCoords);
        }
        this.drawPlayer({ ...p }, pixel);
      });

      // 🏀 Animate the ball independently during a pass
      // const turn = this.turns[this.turnIndex];
      if (turn.ballTrack) {
        const movement = turn.ballTrack.movement || [];
        const [startTime, endTime] = [
          movement[0]?.timestamp,
          movement[1]?.timestamp
        ];
        console.log(`🕒 BallFlight: ${startTime} → ${endTime}, elapsed: ${elapsed}`);
        console.log(
          `🕒 #1 Ball flight from ${movement[0].timestamp} to ${movement[1].timestamp}, elapsed: ${elapsed}`
        );
        console.log(`📍 Ball interpolated position: x=${x}, y=${y}`);

        
        if (movement.length >= 2) {
          const i = getStepIndexForElapsed(movement, elapsed);
          const a = movement[i];
          const b = movement[i + 1] || a;
          const tRaw = b.timestamp === a.timestamp
            ? 1
            : (elapsed - a.timestamp) / (b.timestamp - a.timestamp);
          const t = Math.min(1, Math.max(0, easeInOutQuad(tRaw)));
          const x = a.coords.x + (b.coords.x - a.coords.x) * t;
          const y = a.coords.y + (b.coords.y - a.coords.y) * t;
          const pixel = this.gridToPixels(x, y);
          this.ballCoords = { ...pixel };
          console.log("📍 #3 Ball coords updated to:", this.ballCoords);
        }
      }


      // ✅ Draw ball after players
      if (this.ballCoords && this.ballImage?.complete) {
        const pulse = 1 + 0.3 * Math.sin(currentTime / 100);  // range ~0.9 to 1.1
        const ballSize = 16 * pulse;
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
      if (turn.ballTrack) {
        const lastCoords = turn.ballTrack.movement.at(-1)?.coords;
        if (lastCoords) {
          const pixel = this.gridToPixels(lastCoords.x, lastCoords.y);
          this.ballCoords = { ...pixel };
          console.log("📍 #6 Ball coords updated to:", this.ballCoords);
        }
      } 
      this.activePlayers.forEach(p => {
        const last = p.movement.at(-1);
        const pos = last ? last.coords : this.currentPositions[p.playerId];
        const pixel = this.gridToPixels(pos.x, pos.y);
        this.currentPositions[p.playerId] = pos;
        this.drawPlayer({ ...p }, this.gridToPixels(pos.x, pos.y));
        const movement = p.movement || [];
        const i = getStepIndexForElapsed(movement, elapsed);
        const isBallInFlight = !!turn.ballTrack && elapsed < turn.ballTrack.movement?.[1]?.timestamp;
        console.log(`isBallInFlight: ${isBallInFlight}, elapsed: ${elapsed}, threshold: ${turn.ballTrack.movement[1]?.timestamp}`);
        if (p.hasBallAtStep?.[i] && !isBallInFlight) {
          this.ballCoords = { ...pixel };
          console.log("🎯 Ball attached to", p.pos, p.jersey, "at step", i, this.ballCoords);
        }        
        if (!p.hasBall && turn.ballTrack && p.playerId === turn.ballTrack.movement?.at(-1)?.playerId) {
          const pixel = this.gridToPixels(pos.x, pos.y);
          this.ballCoords = { ...pixel };
          console.log("📍 #5 Ball coords updated to:", this.ballCoords);
        }        
        if (this.ballCoords) {
          console.log("Ball coords:", this.ballCoords);
        } else {
          console.log("No ball coords");
        }        
        
      });        
      if (this.ballCoords && this.ballImage?.complete) {
        const pulse = 1 + 0.3 * Math.sin(currentTime / 100);  // range ~0.9 to 1.1
        const ballSize = 16 * pulse;
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