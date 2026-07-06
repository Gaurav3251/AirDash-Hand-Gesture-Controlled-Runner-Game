"""
entities: Player, Obstacle, and Star for the lane-dodging runner. Kept free
of input handling — entities only expose action-level methods (move_left,
jump, duck, etc.) so game_app can drive them identically regardless of
whether input came from keyboard or gesture.

Obstacle categories:
  "ground"   — sits low (cone, pothole). Avoided by jumping or changing lane.
  "overhead" — sits at head height (barrier). Avoided by ducking or changing lane.
This is what makes both jump and duck gestures meaningful instead of one
being a strictly-better alternative to the other.
"""
import math
import random
import time
import pygame

import config


class Player:
    def __init__(self, lane_count=config.LANE_COUNT,
                 window_width=config.GAME_WINDOW_WIDTH,
                 window_height=config.GAME_WINDOW_HEIGHT):
        self.lane_count = lane_count
        self.window_width = window_width
        self.window_height = window_height
        self.lane_width = window_width // lane_count

        self.current_lane = lane_count // 2
        self.y_base = window_height - 100

        self.standing_width = 46
        self.standing_height = 70
        self.ducking_height = 40  # shorter hitbox while ducking

        self.is_jumping = False
        self._jump_start_time = 0.0
        self.jump_height = 90

        self.is_ducking = False
        self._duck_start_time = 0.0

        self.is_invincible = False
        self._invincible_until = 0.0

        self._run_cycle_start = time.time()

    # --- geometry ---
    @property
    def width(self):
        return self.standing_width

    @property
    def height(self):
        return self.ducking_height if self.is_ducking else self.standing_height

    @property
    def x(self):
        lane_center = self.current_lane * self.lane_width + self.lane_width // 2
        return lane_center - self.width // 2

    @property
    def y(self):
        base = self.y_base + (self.standing_height - self.height)  # feet stay planted when ducking
        if self.is_jumping:
            elapsed = (time.time() - self._jump_start_time) * 1000
            progress = min(elapsed / config.JUMP_DURATION_MS, 1.0)
            if progress >= 1.0:
                self.is_jumping = False
                return base
            arc = 1 - (2 * progress - 1) ** 2  # simple parabolic arc
            return base - int(arc * self.jump_height)
        return base

    @property
    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    # --- actions ---
    def move_left(self):
        self.current_lane = max(0, self.current_lane - 1)

    def move_right(self):
        self.current_lane = min(self.lane_count - 1, self.current_lane + 1)

    def jump(self):
        if not self.is_jumping and not self.is_ducking:
            self.is_jumping = True
            self._jump_start_time = time.time()

    def duck(self):
        if not self.is_jumping:
            self.is_ducking = True
            self._duck_start_time = time.time()

    def grant_invincibility(self, duration_seconds=config.INVINCIBILITY_AFTER_HIT_SECONDS):
        self.is_invincible = True
        self._invincible_until = time.time() + duration_seconds

    def update(self):
        if self.is_ducking:
            elapsed_ms = (time.time() - self._duck_start_time) * 1000
            if elapsed_ms >= config.DUCK_DURATION_MS:
                self.is_ducking = False
        if self.is_invincible and time.time() > self._invincible_until:
            self.is_invincible = False

    # --- rendering: simple humanoid runner, not a vehicle ---
    def draw(self, surface):
        rect = self.rect
        blink_hidden = self.is_invincible and int(time.time() * 8) % 2 == 0
        if blink_hidden:
            return  # brief flicker to signal post-hit invincibility

        skin = (247, 200, 160)
        shirt = (66, 150, 245)
        pants = (45, 55, 75)

        head_r = max(8, rect.width // 5)
        head_center = (rect.centerx, rect.top + head_r + 2)
        torso_top = head_center[1] + head_r - 2
        torso_bottom = rect.bottom - (14 if not self.is_ducking else 6)

        # torso
        pygame.draw.rect(
            surface, shirt,
            pygame.Rect(rect.left + 6, torso_top, rect.width - 12, max(6, torso_bottom - torso_top)),
            border_radius=8,
        )
        # legs (simple running stance; shorter/spread when ducking)
        leg_w = max(6, rect.width // 5)
        leg_y = torso_bottom
        leg_h = max(4, rect.bottom - leg_y)
        pygame.draw.rect(surface, pants, (rect.left + 8, leg_y, leg_w, leg_h), border_radius=4)
        pygame.draw.rect(surface, pants, (rect.right - 8 - leg_w, leg_y, leg_w, leg_h), border_radius=4)
        # arms
        pygame.draw.line(surface, skin, (rect.left + 4, torso_top + 6), (rect.left - 4, torso_bottom - 6), 5)
        pygame.draw.line(surface, skin, (rect.right - 4, torso_top + 6), (rect.right + 4, torso_bottom - 6), 5)
        # head
        pygame.draw.circle(surface, skin, head_center, head_r)

        if self.is_invincible:
            pygame.draw.circle(surface, (255, 230, 90), rect.center, max(rect.width, rect.height) // 2 + 6, 2)


class Obstacle:
    GROUND_KINDS = ("cone", "pothole")
    OVERHEAD_KINDS = ("barrier",)

    def __init__(self, lane, speed, kind=None, lane_count=config.LANE_COUNT,
                 window_width=config.GAME_WINDOW_WIDTH):
        self.lane = lane
        self.speed = speed
        self.kind = kind or random.choice(self.GROUND_KINDS + self.OVERHEAD_KINDS)
        self.category = "overhead" if self.kind in self.OVERHEAD_KINDS else "ground"
        self.lane_width = window_width // lane_count

        dimensions = {
            "cone": (44, 50),
            "pothole": (60, 26),
            "barrier": (70, 26),  # thin bar at head height — duck under it
        }
        self.width, self.height = dimensions[self.kind]
        self.y = -self.height

    @property
    def x(self):
        lane_center = self.lane * self.lane_width + self.lane_width // 2
        return lane_center - self.width // 2

    @property
    def y_offset_for_category(self):
        # Overhead obstacles float near head height above the running lane
        # instead of sitting on the ground.
        return 34 if self.category == "overhead" else 0

    @property
    def rect(self):
        return pygame.Rect(self.x, int(self.y) + self.y_offset_for_category, self.width, self.height)

    def update(self):
        self.y += self.speed

    def is_off_screen(self, window_height=config.GAME_WINDOW_HEIGHT):
        return self.y > window_height

    def draw(self, surface):
        rect = self.rect
        if self.kind == "cone":
            pygame.draw.polygon(
                surface, (245, 120, 35),
                [(rect.centerx, rect.top), (rect.left, rect.bottom), (rect.right, rect.bottom)],
            )
            pygame.draw.rect(surface, (255, 235, 170), (rect.left + 8, rect.bottom - 12, rect.width - 16, 5))
        elif self.kind == "pothole":
            pygame.draw.ellipse(surface, (30, 28, 30), rect)
            pygame.draw.ellipse(surface, (70, 65, 70), rect.inflate(-16, -8), 2)
        elif self.kind == "barrier":
            pygame.draw.rect(surface, (200, 60, 60), rect, border_radius=4)
            for offset in range(-10, rect.width, 20):
                pygame.draw.line(
                    surface, (255, 230, 120),
                    (rect.left + offset, rect.bottom), (rect.left + offset + 14, rect.top), 4,
                )


class Star:
    """Falling collectible: grants bonus points and a temporary score multiplier."""

    def __init__(self, lane, speed, lane_count=config.LANE_COUNT,
                 window_width=config.GAME_WINDOW_WIDTH):
        self.lane = lane
        self.speed = speed
        self.lane_width = window_width // lane_count
        self.size = 34
        self.y = -self.size
        self.collected = False

    @property
    def x(self):
        lane_center = self.lane * self.lane_width + self.lane_width // 2
        return lane_center - self.size // 2

    @property
    def rect(self):
        return pygame.Rect(self.x, int(self.y), self.size, self.size)

    def update(self):
        self.y += self.speed

    def is_off_screen(self, window_height=config.GAME_WINDOW_HEIGHT):
        return self.y > window_height

    def draw(self, surface):
        rect = self.rect
        cx, cy = rect.center
        r_outer, r_inner = self.size // 2, self.size // 4
        points = []
        for i in range(10):
            angle = -90 + i * 36
            r = r_outer if i % 2 == 0 else r_inner
            points.append((
                cx + r * math.cos(math.radians(angle)),
                cy + r * math.sin(math.radians(angle)),
            ))
        pygame.draw.polygon(surface, (255, 221, 64), points)
        pygame.draw.polygon(surface, (255, 245, 180), points, 2)
