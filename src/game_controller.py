"""
game_controller: translates approved input (gesture labels from the
stability filter, or keyboard keys) into game actions. The game itself only
ever sees actions from config (ACTION_MOVE_LEFT etc.), never gestures or
key codes directly — this is what lets keyboard mode and gesture mode share
one game implementation, and it's the seam where a future accessibility
mode would remap gestures without touching the game.
"""
import pygame

import config


class GameController:
    def __init__(self, gesture_action_map=None):
        self.gesture_action_map = gesture_action_map or config.DEFAULT_GESTURE_ACTION_MAP

    def gesture_to_action(self, gesture_label):
        return self.gesture_action_map.get(gesture_label, config.ACTION_NONE)

    def keyboard_to_action(self, pygame_key):
        mapping = {
            pygame.K_LEFT: config.ACTION_MOVE_LEFT,
            pygame.K_RIGHT: config.ACTION_MOVE_RIGHT,
            pygame.K_UP: config.ACTION_JUMP,
            pygame.K_DOWN: config.ACTION_DUCK,
            pygame.K_p: config.ACTION_PAUSE,
            pygame.K_SPACE: config.ACTION_EXTRA_LIFE,
        }
        return mapping.get(pygame_key, config.ACTION_NONE)
