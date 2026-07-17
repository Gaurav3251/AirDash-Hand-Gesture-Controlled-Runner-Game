// gameCanvas.js: HTML5 Canvas implementation of the AirDash runner game.
// Keeps track of the game loop, collisions, scores, and lifelines.

const CONFIG = {
  WIDTH: 800,
  HEIGHT: 600,
  LANE_COUNT: 3,
  OBSTACLE_SPEED_START: 3.5, // Decreased from 6.0
  OBSTACLE_SPEED_INCREMENT: 0.05, // Decreased from 0.15
  OBSTACLE_SPAWN_INTERVAL_MS: 1500, // Increased from 1100
  STAR_SPAWN_INTERVAL_MS: 5000, // Increased from 4000
  JUMP_DURATION_MS: 600, // Increased from 450
  DUCK_DURATION_MS: 700, // Increased from 550
  INVINCIBILITY_MS: 1200,
  STAR_DURATION_MS: 10000,
  INITIAL_LIVES: 3,
  MAX_LIVES: 3,
  MAX_LIFELINES: 3,
  STAR_BONUS_SCORE: 50,
};

class Player {
  constructor() {
    this.lane = 1; // 0, 1, 2
    this.width = 46;
    this.standingHeight = 70;
    this.duckingHeight = 40;
    this.yBase = CONFIG.HEIGHT - 100;
    
    this.isJumping = false;
    this.jumpStartTime = 0;
    this.jumpHeight = 90;
    
    this.isDucking = false;
    this.duckStartTime = 0;
    
    this.isInvincible = false;
    this.invincibleUntil = 0;
  }

  get height() {
    return this.isDucking ? this.duckingHeight : this.standingHeight;
  }

  get x() {
    const laneWidth = CONFIG.WIDTH / CONFIG.LANE_COUNT;
    const laneCenter = this.lane * laneWidth + laneWidth / 2;
    return laneCenter - this.width / 2;
  }

  get y() {
    const base = this.yBase + (this.standingHeight - this.height);
    if (this.isJumping) {
      const elapsed = Date.now() - this.jumpStartTime;
      const progress = Math.min(elapsed / CONFIG.JUMP_DURATION_MS, 1.0);
      if (progress >= 1.0) {
        this.isJumping = false;
        return base;
      }
      // Simple parabolic arc
      const arc = 1 - (2 * progress - 1) ** 2;
      return base - arc * this.jumpHeight;
    }
    return base;
  }

  get rect() {
    return {
      x: this.x,
      y: this.y,
      width: this.width,
      height: this.height,
    };
  }

  moveLeft() {
    this.lane = Math.max(0, this.lane - 1);
  }

  moveRight() {
    this.lane = Math.min(CONFIG.LANE_COUNT - 1, this.lane + 1);
  }

  jump() {
    if (!this.isJumping && !this.isDucking) {
      this.isJumping = true;
      this.jumpStartTime = Date.now();
    }
  }

  duck() {
    if (!this.isJumping) {
      this.isDucking = true;
      this.duckStartTime = Date.now();
    }
  }

  grantInvincibility() {
    this.isInvincible = true;
    this.invincibleUntil = Date.now() + CONFIG.INVINCIBILITY_MS;
  }

  update() {
    const now = Date.now();
    if (this.isDucking) {
      const elapsed = now - this.duckStartTime;
      if (elapsed >= CONFIG.DUCK_DURATION_MS) {
        this.isDucking = false;
      }
    }
    if (this.isInvincible && now > this.invincibleUntil) {
      this.isInvincible = false;
    }
  }

  draw(ctx) {
    const rect = this.rect;
    
    // Invincibility flashing
    if (this.isInvincible && Math.floor(Date.now() / 125) % 2 === 0) {
      return;
    }

    const skin = "#f7c8a0";
    const shirt = "#2e86de";
    const pants = "#2c3e50";

    const headR = Math.max(8, this.width / 5);
    const headCX = rect.x + rect.width / 2;
    const headCY = rect.y + headR + 2;
    const torsoTop = headCY + headR - 2;
    const torsoBottom = rect.y + rect.height - (this.isDucking ? 6 : 14);

    // Draw torso
    ctx.fillStyle = shirt;
    ctx.beginPath();
    ctx.roundRect(rect.x + 6, torsoTop, rect.width - 12, Math.max(6, torsoBottom - torsoTop), 8);
    ctx.fill();

    // Draw legs
    const legW = Math.max(6, this.width / 5);
    const legY = torsoBottom;
    const legH = rect.y + rect.height - legY;
    
    ctx.fillStyle = pants;
    ctx.beginPath();
    ctx.roundRect(rect.x + 8, legY, legW, legH, 4);
    ctx.roundRect(rect.x + rect.width - 8 - legW, legY, legW, legH, 4);
    ctx.fill();

    // Draw arms
    ctx.strokeStyle = skin;
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(rect.x + 4, torsoTop + 6);
    ctx.lineTo(rect.x - 4, torsoBottom - 6);
    ctx.moveTo(rect.x + rect.width - 4, torsoTop + 6);
    ctx.lineTo(rect.x + rect.width + 4, torsoBottom - 6);
    ctx.stroke();

    // Draw head
    ctx.fillStyle = skin;
    ctx.beginPath();
    ctx.arc(headCX, headCY, headR, 0, Math.PI * 2);
    ctx.fill();

    // Invincibility shield ring
    if (this.isInvincible) {
      ctx.strokeStyle = "#ffe259";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(rect.x + rect.width / 2, rect.y + rect.height / 2, Math.max(rect.width, rect.height) / 2 + 6, 0, Math.PI * 2);
      ctx.stroke();
    }
  }
}

class Obstacle {
  constructor(lane, speed) {
    this.lane = lane;
    this.speed = speed;
    
    const kinds = ["cone", "pothole", "barrier"];
    this.kind = kinds[Math.floor(Math.random() * kinds.length)];
    this.category = this.kind === "barrier" ? "overhead" : "ground";
    
    const dimensions = {
      cone: { w: 44, h: 50 },
      pothole: { w: 60, h: 26 },
      barrier: { w: 70, h: 26 },
    };
    
    this.width = dimensions[this.kind].w;
    this.height = dimensions[this.kind].h;
    this.y = -this.height;
  }

  get x() {
    const laneWidth = CONFIG.WIDTH / CONFIG.LANE_COUNT;
    const laneCenter = this.lane * laneWidth + laneWidth / 2;
    return laneCenter - this.width / 2;
  }

  get yOffset() {
    return this.category === "overhead" ? 34 : 0;
  }

  get rect() {
    return {
      x: this.x,
      y: this.y + this.yOffset,
      width: this.width,
      height: this.height,
    };
  }

  update() {
    this.y += this.speed;
  }

  isOffScreen() {
    return this.y > CONFIG.HEIGHT;
  }

  draw(ctx) {
    const rect = this.rect;
    if (this.kind === "cone") {
      // Orange cone
      ctx.fillStyle = "#f39c12";
      ctx.beginPath();
      ctx.moveTo(rect.x + rect.width / 2, rect.y);
      ctx.lineTo(rect.x, rect.y + rect.height);
      ctx.lineTo(rect.x + rect.width, rect.y + rect.height);
      ctx.closePath();
      ctx.fill();

      // White stripe
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.moveTo(rect.x + rect.width / 2, rect.y + rect.height * 0.4);
      ctx.lineTo(rect.x + rect.width * 0.25, rect.y + rect.height * 0.7);
      ctx.lineTo(rect.x + rect.width * 0.75, rect.y + rect.height * 0.7);
      ctx.closePath();
      ctx.fill();
    } else if (this.kind === "pothole") {
      // Dark grey ellipse
      ctx.fillStyle = "#1e1c1e";
      ctx.beginPath();
      ctx.ellipse(rect.x + rect.width / 2, rect.y + rect.height / 2, rect.width / 2, rect.height / 2, 0, 0, Math.PI * 2);
      ctx.fill();
      
      ctx.strokeStyle = "#464146";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(rect.x + rect.width / 2, rect.y + rect.height / 2, rect.width / 3, rect.height / 3, 0, 0, Math.PI * 2);
      ctx.stroke();
    } else if (this.kind === "barrier") {
      // Construction-style low clearance archway/gate
      const beamY = rect.y;
      const beamH = rect.height;
      
      // Draw left & right support posts
      ctx.fillStyle = "#7f8c8d"; // metallic grey
      ctx.fillRect(rect.x + 2, beamY, 6, beamH + 24);
      ctx.fillRect(rect.x + rect.width - 8, beamY, 6, beamH + 24);
      
      // Draw top crossbeam
      ctx.fillStyle = "#f1c40f"; // bright yellow
      ctx.fillRect(rect.x, beamY, rect.width, beamH);
      
      // Draw black hazard stripes on crossbeam
      ctx.fillStyle = "#2c3e50"; // dark charcoal/black
      ctx.beginPath();
      for (let offset = 4; offset < rect.width; offset += 20) {
        ctx.moveTo(rect.x + offset, beamY + beamH);
        ctx.lineTo(rect.x + offset + 8, beamY);
        ctx.lineTo(rect.x + offset + 14, beamY);
        ctx.lineTo(rect.x + offset + 6, beamY + beamH);
        ctx.closePath();
      }
      ctx.fill();
      
      // Draw a small red flashing light in the center of the beam (representing alert, NO words!)
      const pulse = Math.sin(Date.now() / 150) * 0.2 + 0.8;
      ctx.fillStyle = `rgba(231, 76, 60, ${pulse})`;
      ctx.beginPath();
      ctx.arc(rect.x + rect.width / 2, beamY + beamH / 2, 5, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

class Star {
  constructor(lane, speed) {
    this.lane = lane;
    this.speed = speed;
    this.size = 34;
    this.y = -this.size;
    this.collected = false;
  }

  get x() {
    const laneWidth = CONFIG.WIDTH / CONFIG.LANE_COUNT;
    const laneCenter = this.lane * laneWidth + laneWidth / 2;
    return laneCenter - this.size / 2;
  }

  get rect() {
    return {
      x: this.x,
      y: this.y,
      width: this.size,
      height: this.size,
    };
  }

  update() {
    this.y += this.speed;
  }

  isOffScreen() {
    return this.y > CONFIG.HEIGHT;
  }

  draw(ctx) {
    if (this.collected) return;
    
    const rect = this.rect;
    const cx = rect.x + this.size / 2;
    const cy = rect.y + this.size / 2;
    const rOuter = this.size / 2;
    const rInner = this.size / 4;

    ctx.fillStyle = "#ffdd59";
    ctx.strokeStyle = "#fff5b4";
    ctx.lineWidth = 2;

    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const angle = -Math.PI / 2 + (i * Math.PI) / 5;
      const r = i % 2 === 0 ? rOuter : rInner;
      ctx.lineTo(cx + r * Math.cos(angle), cy + r * Math.sin(angle));
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
}

export class Game {
  constructor() {
    this.player = new Player();
    this.obstacles = [];
    this.stars = [];
    this.speed = CONFIG.OBSTACLE_SPEED_START;
    this.score = 0;
    this.lives = CONFIG.INITIAL_LIVES;
    this.lifelinesUsed = 0;
    this.gameOver = false;
    this.paused = false;
    this.doubleScoreUntil = 0;
    this.revivePending = false;
    this.reviveTimeLimit = 0;
    
    this.lastSpawnTime = 0;
    this.lastStarSpawnTime = 0;
    this.startTime = Date.now();
  }

  reset() {
    this.player = new Player();
    this.obstacles = [];
    this.stars = [];
    this.speed = CONFIG.OBSTACLE_SPEED_START;
    this.score = 0;
    this.lives = CONFIG.INITIAL_LIVES;
    this.lifelinesUsed = 0;
    this.gameOver = false;
    this.paused = false;
    this.doubleScoreUntil = 0;
    this.revivePending = false;
    this.reviveTimeLimit = 0;
    this.lastSpawnTime = Date.now();
    this.lastStarSpawnTime = Date.now();
    this.startTime = Date.now();
  }

  isDoubleScore() {
    return Date.now() < this.doubleScoreUntil;
  }

  applyAction(action) {
    if (!action || action === "none") return;

    if (action === "pause") {
      if (this.gameOver) {
        this.reset();
      } else {
        this.paused = !this.paused;
      }
      return;
    }

    if (action === "stop") {
      if (!this.gameOver) {
        this.gameOver = true;
      }
      return;
    }

    // Allow revive action even when paused/frozen during revive countdown!
    if (action === "extra_life") {
      if (this.revivePending) {
        this.lives = 1;
        this.lifelinesUsed += 1;
        this.revivePending = false;
        this.paused = false;
        this.player.grantInvincibility();
        return;
      }
    }

    if (this.paused || this.gameOver) {
      return;
    }

    if (action === "move_left") {
      this.player.moveLeft();
    } else if (action === "move_right") {
      this.player.moveRight();
    } else if (action === "jump") {
      this.player.jump();
    } else if (action === "duck") {
      this.player.duck();
    } else if (action === "extra_life") {
      if (this.lifelinesUsed < CONFIG.MAX_LIFELINES && this.lives < CONFIG.MAX_LIVES) {
        this.lives += 1;
        this.lifelinesUsed += 1;
      }
    }
  }

  update() {
    if (this.revivePending) {
      if (Date.now() > this.reviveTimeLimit) {
        this.revivePending = false;
        this.gameOver = true;
      }
      return;
    }

    if (this.paused || this.gameOver) return;

    this.player.update();
    const now = Date.now();

    // Spawning obstacles
    if (now - this.lastSpawnTime > CONFIG.OBSTACLE_SPAWN_INTERVAL_MS) {
      const lane = Math.floor(Math.random() * CONFIG.LANE_COUNT);
      this.obstacles.push(new Obstacle(lane, this.speed));
      this.lastSpawnTime = now;
      this.speed += CONFIG.OBSTACLE_SPEED_INCREMENT;
    }

    // Spawning stars
    if (now - this.lastStarSpawnTime > CONFIG.STAR_SPAWN_INTERVAL_MS) {
      const lane = Math.floor(Math.random() * CONFIG.LANE_COUNT);
      this.stars.push(new Star(lane, this.speed));
      this.lastStarSpawnTime = now;
    }

    // Update entities
    this.obstacles.forEach((o) => o.update());
    this.obstacles = this.obstacles.filter((o) => !o.isOffScreen());

    this.stars.forEach((s) => s.update());
    this.stars = this.stars.filter((s) => !s.isOffScreen() && !s.collected);

    // Collisions
    this._checkObstacleCollisions();
    this._checkStarPickups();

    if (!this.gameOver) {
      this.score += this.isDoubleScore() ? 2 : 1;
    }
  }

  _checkObstacleCollisions() {
    if (this.player.isInvincible) return;

    const pRect = this.player.rect;
    for (const obstacle of this.obstacles) {
      const oRect = obstacle.rect;
      
      // Rect overlap
      const overlap =
        pRect.x < oRect.x + oRect.width &&
        pRect.x + pRect.width > oRect.x &&
        pRect.y < oRect.y + oRect.height &&
        pRect.y + pRect.height > oRect.y;

      if (!overlap) continue;

      // Check dodge
      const avoided =
        (obstacle.category === "ground" && this.player.isJumping && this.player.y < oRect.y - 10) ||
        (obstacle.category === "overhead" && this.player.isDucking);

      if (avoided) continue;

      // Hit registered
      this.lives -= 1;
      if (this.lives <= 0) {
        this.lives = 0;
        if (this.lifelinesUsed < CONFIG.MAX_LIFELINES) {
          this.revivePending = true;
          this.paused = true;
          this.reviveTimeLimit = Date.now() + 5000; // 5 seconds to revive
        } else {
          this.gameOver = true;
        }
      } else {
        this.player.grantInvincibility();
      }
      break; // handle one collision per frame
    }
  }

  _checkStarPickups() {
    const pRect = this.player.rect;
    for (const star of this.stars) {
      if (star.collected) continue;

      const sRect = star.rect;
      const overlap =
        pRect.x < sRect.x + sRect.width &&
        pRect.x + pRect.width > sRect.x &&
        pRect.y < sRect.y + sRect.height &&
        pRect.y + pRect.height > sRect.y;

      if (overlap) {
        star.collected = true;
        this.score += CONFIG.STAR_BONUS_SCORE;
        this.doubleScoreUntil = Date.now() + CONFIG.STAR_DURATION_MS;
      }
    }
  }

  draw(ctx) {
    // Clear screen with a beautiful deep background color
    ctx.fillStyle = "#121218";
    ctx.fillRect(0, 0, CONFIG.WIDTH, CONFIG.HEIGHT);

    // Draw lane road track
    const roadX = 70;
    const roadW = CONFIG.WIDTH - 140;
    
    ctx.fillStyle = "#22242c";
    ctx.fillRect(roadX, 0, roadW, CONFIG.HEIGHT);
    
    // Draw borders
    ctx.strokeStyle = "#50505a";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(roadX, 0);
    ctx.lineTo(roadX, CONFIG.HEIGHT);
    ctx.moveTo(roadX + roadW, 0);
    ctx.lineTo(roadX + roadW, CONFIG.HEIGHT);
    ctx.stroke();

    // Grass margins
    ctx.fillStyle = "#187846";
    ctx.fillRect(0, 0, roadX, CONFIG.HEIGHT);
    ctx.fillRect(roadX + roadW, 0, roadX, CONFIG.HEIGHT);

    // Lane dividing lines
    const laneWidth = CONFIG.WIDTH / CONFIG.LANE_COUNT;
    ctx.strokeStyle = "#ebeb78";
    ctx.lineWidth = 3;
    
    for (let i = 1; i < CONFIG.LANE_COUNT; i++) {
      const x = i * laneWidth;
      ctx.setLineDash([22, 20]);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, CONFIG.HEIGHT);
      ctx.stroke();
    }
    ctx.setLineDash([]); // Reset line dash

    // Draw entities
    this.obstacles.forEach((o) => o.draw(ctx));
    this.stars.forEach((s) => s.draw(ctx));
    this.player.draw(ctx);

    // HUD Info
    this._drawHUD(ctx);

    // Revive overlay
    if (this.revivePending) {
      const remaining = Math.max(0, Math.ceil((this.reviveTimeLimit - Date.now()) / 1000));
      this._drawCenterOverlay(ctx, `REVIVE? Point index finger UP! (${remaining}s)`);
    } else if (this.paused && !this.gameOver) {
      // Paused Overlay
      this._drawCenterOverlay(ctx, "PAUSED — Thumbs Up to resume");
    } else if (this.gameOver) {
      // Game Over Overlay
      this._drawCenterOverlay(ctx, "GAME OVER — Thumbs Up to restart");
    }
  }

  _drawHUD(ctx) {
    ctx.fillStyle = "#e0e0e0";
    ctx.font = "bold 22px 'Outfit', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(`Score: ${this.score}`, 16, 32);

    // Draw lives
    const heartActive = "❤️ ";
    const heartEmpty = "🖤 ";
    let livesText = "";
    for (let i = 0; i < CONFIG.MAX_LIVES; i++) {
      livesText += i < this.lives ? heartActive : heartEmpty;
    }
    ctx.font = "20px 'Outfit', sans-serif";
    ctx.fillText(livesText.trim(), 16, 68);

    // Draw lifelines count remaining
    const lifelinesRemaining = CONFIG.MAX_LIFELINES - this.lifelinesUsed;
    ctx.fillStyle = "#ffe259";
    ctx.font = "600 13px 'Outfit', sans-serif";
    ctx.fillText(`Lifelines Left: ${lifelinesRemaining}/${CONFIG.MAX_LIFELINES}`, 16, 96);

    // Draw elapsed time
    const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
    ctx.fillStyle = "#aaaaaa";
    ctx.font = "16px 'Outfit', sans-serif";
    ctx.fillText(`Time: ${elapsed}s`, 16, 126);

    // Double score indicator
    if (this.isDoubleScore()) {
      const remaining = Math.max(0, Math.ceil((this.doubleScoreUntil - Date.now()) / 1000));
      ctx.fillStyle = "#ffe259";
      ctx.font = "bold 16px 'Outfit', sans-serif";
      ctx.fillText(`2x SCORE (${remaining}s)`, 16, 156);
    }
  }

  _drawCenterOverlay(ctx, text) {
    ctx.font = "600 24px 'Outfit', sans-serif";
    ctx.textAlign = "center";
    
    const textWidth = ctx.measureText(text).width;
    const paddingX = 30;
    const paddingY = 20;
    const boxW = textWidth + paddingX * 2;
    const boxH = 64;
    
    ctx.fillStyle = "rgba(0,0,0,0.85)";
    ctx.strokeStyle = "#50505a";
    ctx.lineWidth = 2;
    
    const boxX = CONFIG.WIDTH / 2 - boxW / 2;
    const boxY = CONFIG.HEIGHT / 2 - boxH / 2;
    
    ctx.beginPath();
    ctx.roundRect(boxX, boxY, boxW, boxH, 12);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = "#ffffff";
    ctx.textBaseline = "middle";
    ctx.fillText(text, CONFIG.WIDTH / 2, CONFIG.HEIGHT / 2);
    ctx.textBaseline = "alphabetic"; // restore default
  }
}
