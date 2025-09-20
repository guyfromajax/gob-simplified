const MathStub = {
  Between(min, max) {
    const lower = Math.ceil(Math.min(min, max));
    const upper = Math.floor(Math.max(min, max));
    if (!Number.isFinite(lower) || !Number.isFinite(upper)) return lower;
    return Math.floor((lower + upper) / 2);
  },
  Clamp(value, min, max) {
    if (min > max) [min, max] = [max, min];
    return Math.max(min, Math.min(max, value));
  },
  Distance: {
    Between(x1, y1, x2, y2) {
      const dx = (x2 ?? 0) - (x1 ?? 0);
      const dy = (y2 ?? 0) - (y1 ?? 0);
      return Math.hypot(dx, dy);
    },
  },
  Vector2: class {
    constructor(x = 0, y = 0) {
      this.x = x;
      this.y = y;
    }
  },
};

const Curves = {
  QuadraticBezier: class {
    constructor(p0, p1, p2) {
      this.p0 = p0;
      this.p1 = p1;
      this.p2 = p2;
    }
    getPoint(t) {
      const u = 1 - t;
      const u2 = u * u;
      const t2 = t * t;
      const x = u2 * this.p0.x + 2 * u * t * this.p1.x + t2 * this.p2.x;
      const y = u2 * this.p0.y + 2 * u * t * this.p1.y + t2 * this.p2.y;
      return { x, y };
    }
  }
};

const PhaserStub = { Math: MathStub, Curves };

export { MathStub as Math, Curves };
export default PhaserStub;
