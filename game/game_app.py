"""
game_app: the demo game itself — a lane-dodging runner with lives, ducking,
jumping, and star powerups. It knows nothing about gestures or keyboards;
it only reacts to action strings from config (ACTION_MOVE_LEFT, ACTION_JUMP,
...). This is what lets main.py drive it identically from keyboard input or
the gesture pipeline.

Call pattern (see main.py for the real loop):
    game = GameApp()
    while game.running:
        game.handle_pygame_events()
        game.apply_action(action)       # action from keyboard or gesture
        game.update()
        game.draw(overlay_surface=camera_pip)
        pygame.display.flip()
        game.tick()
"""
import random
import time

import pygame

import config
from game.entities import Player, Obstacle, Star


class GameApp:
    def __init__(self, screen=None):
        pygame.init()
        pygame.font.init()
        self.screen = screen or pygame.display.set_mode(
            (config.GAME_WINDOW_WIDTH, config.GAME_WINDOW_HEIGHT)
        )
        pygame.display.set_caption("Gesture Runner — MVP")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 22)
        self.font_small = pygame.font.SysFont("consolas", 16)
        self.font_tiny = pygame.font.SysFont("consolas", 13)

        self.running = True
        self.reset()

    def reset(self):
        self.player = Player()
        self.obstacles = []
        self.stars = []
        self.speed = config.OBSTACLE_SPEED_START
        self.score = 0
        self.lives = config.INITIAL_LIVES
        self.game_over = False
        self.paused = False
        self.double_score_until = 0.0
        self._last_spawn_time = pygame.time.get_ticks()
        self._last_star_spawn_time = pygame.time.get_ticks()
        self._start_time = time.time()

    # --- input ---
    def handle_pygame_events(self):
        """Processes quit/window events. Returns False if the app should exit."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False
                return False
        return True

    def apply_action(self, action):
        """Applies one action-per-call semantics. `action` is a config.ACTION_* string or None."""
        if action is None or action == config.ACTION_NONE:
            return

        if action == config.ACTION_PAUSE:
            if self.game_over:
                self.reset()
            else:
                self.paused = not self.paused
            return

        if action == config.ACTION_STOP:
            # Hard stop: ends the run immediately, distinct from pause.
            if not self.game_over:
                self.game_over = True
            return

        if self.paused or self.game_over:
            return

        if action == config.ACTION_MOVE_LEFT:
            self.player.move_left()
        elif action == config.ACTION_MOVE_RIGHT:
            self.player.move_right()
        elif action == config.ACTION_JUMP:
            self.player.jump()
        elif action == config.ACTION_DUCK:
            self.player.duck()
        elif action == config.ACTION_EXTRA_LIFE:
            self.lives = min(config.MAX_LIVES, self.lives + 1)

    # --- simulation ---
    def update(self):
        if self.paused or self.game_over:
            return

        self.player.update()
        now = pygame.time.get_ticks()

        if now - self._last_spawn_time > config.OBSTACLE_SPAWN_INTERVAL_MS:
            lane = random.randint(0, config.LANE_COUNT - 1)
            self.obstacles.append(Obstacle(lane, self.speed))
            self._last_spawn_time = now
            self.speed += config.OBSTACLE_SPEED_INCREMENT

        if now - self._last_star_spawn_time > config.STAR_SPAWN_INTERVAL_MS:
            lane = random.randint(0, config.LANE_COUNT - 1)
            self.stars.append(Star(lane, self.speed))
            self._last_star_spawn_time = now

        for obstacle in self.obstacles:
            obstacle.update()
        self.obstacles = [o for o in self.obstacles if not o.is_off_screen()]

        for star in self.stars:
            star.update()
        self.stars = [s for s in self.stars if not s.is_off_screen() and not s.collected]

        self._check_obstacle_collisions()
        self._check_star_pickups()

        if not self.game_over:
            self.score += 2 if self._is_double_score() else 1

    def _check_obstacle_collisions(self):
        if self.player.is_invincible:
            return
        for obstacle in self.obstacles:
            if not obstacle.rect.colliderect(self.player.rect):
                continue

            avoided = (
                (obstacle.category == "ground" and self.player.is_jumping
                 and self.player.y < obstacle.rect.top - 10)
                or (obstacle.category == "overhead" and self.player.is_ducking)
            )
            if avoided:
                continue

            self._register_hit()
            break  # one hit per frame is enough

    def _register_hit(self):
        self.lives -= 1
        if self.lives <= 0:
            self.lives = 0
            self.game_over = True
        else:
            self.player.grant_invincibility()

    def _check_star_pickups(self):
        for star in self.stars:
            if star.collected:
                continue
            if star.rect.colliderect(self.player.rect):
                star.collected = True
                self.score += config.STAR_SCORE_VALUE
                self.double_score_until = time.time() + config.STAR_DOUBLE_SCORE_SECONDS

    def _is_double_score(self):
        return time.time() < self.double_score_until

    # --- rendering ---
    def draw(self, overlay_surface=None, overlay_caption=None):
        self.screen.fill((18, 18, 24))
        self._draw_track()
        for obstacle in self.obstacles:
            obstacle.draw(self.screen)
        for star in self.stars:
            if not star.collected:
                star.draw(self.screen)
        self.player.draw(self.screen)
        self._draw_hud()

        if self.paused and not self.game_over:
            self._draw_center_text("PAUSED — open palm to resume")
        if self.game_over:
            self._draw_center_text("GAME OVER — open palm or P to restart")

        if overlay_surface is not None:
            self._draw_pip(overlay_surface, overlay_caption)

    def _draw_track(self):
        road_rect = pygame.Rect(70, 0, config.GAME_WINDOW_WIDTH - 140, config.GAME_WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, (34, 36, 44), road_rect)
        pygame.draw.rect(self.screen, (80, 80, 90), road_rect, 4)
        pygame.draw.rect(self.screen, (24, 120, 70), (0, 0, 70, config.GAME_WINDOW_HEIGHT))
        pygame.draw.rect(
            self.screen, (24, 120, 70),
            (config.GAME_WINDOW_WIDTH - 70, 0, 70, config.GAME_WINDOW_HEIGHT),
        )
        lane_width = config.GAME_WINDOW_WIDTH // config.LANE_COUNT
        for i in range(1, config.LANE_COUNT):
            x = i * lane_width
            for y in range(0, config.GAME_WINDOW_HEIGHT, 42):
                pygame.draw.line(self.screen, (235, 235, 120), (x, y), (x, y + 22), 3)

    def _draw_hud(self):
        score_surf = self.font.render(f"Score: {self.score}", True, (230, 230, 230))
        self.screen.blit(score_surf, (12, 12))

        lives_text = "♥ " * self.lives + "· " * (config.MAX_LIVES - self.lives)
        lives_surf = self.font.render(lives_text.strip(), True, (255, 90, 110))
        self.screen.blit(lives_surf, (12, 42))

        elapsed = int(time.time() - self._start_time)
        time_surf = self.font_small.render(f"Time: {elapsed}s", True, (170, 170, 170))
        self.screen.blit(time_surf, (12, 72))

        if self._is_double_score():
            remaining = self.double_score_until - time.time()
            boost_surf = self.font_small.render(f"2x SCORE ({remaining:.0f}s)", True, (255, 221, 64))
            self.screen.blit(boost_surf, (12, 94))

        gesture_surf = self.font_tiny.render(
            "swipe=lane  slide up=jump  slide down=duck  thumbs=+life  "
            "palm=pause/resume  fist=stop",
            True, (180, 190, 200),
        )
        self.screen.blit(gesture_surf, (12, config.GAME_WINDOW_HEIGHT - 22))

    def _draw_center_text(self, text):
        surf = self.font.render(text, True, (255, 255, 255))
        rect = surf.get_rect(center=(config.GAME_WINDOW_WIDTH // 2, config.GAME_WINDOW_HEIGHT // 2))
        pygame.draw.rect(self.screen, (0, 0, 0), rect.inflate(24, 20))
        self.screen.blit(surf, rect)

    def _draw_pip(self, overlay_surface, caption=None):
        pip_x = config.GAME_WINDOW_WIDTH - config.OVERLAY_PIP_WIDTH - 12
        pip_y = 12
        self.screen.blit(overlay_surface, (pip_x, pip_y))
        pygame.draw.rect(
            self.screen, (90, 90, 100),
            (pip_x, pip_y, config.OVERLAY_PIP_WIDTH, config.OVERLAY_PIP_HEIGHT), 2,
        )
        if caption:
            cap_surf = self.font_small.render(caption, True, (230, 230, 230))
            self.screen.blit(cap_surf, (pip_x, pip_y + config.OVERLAY_PIP_HEIGHT + 4))

    def tick(self):
        return self.clock.tick(config.GAME_FPS)

    def quit(self):
        pygame.quit()
