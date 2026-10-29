from enum import Enum, auto


class CellValue(Enum):
    EMPTY = 0
    FOOD = -1


class CellType(Enum):
    EMPTY = auto()
    FOOD = auto()
    HEAD_UP = auto()
    HEAD_LEFT = auto()
    HEAD_RIGHT = auto()
    HEAD_DOWN = auto()
    BODY_HORZ = auto()
    BODY_VERT = auto()
    BODY_TURN_UL = auto()
    BODY_TURN_UR = auto()
    BODY_TURN_DL = auto()
    BODY_TURN_DR = auto()


class CellColor(Enum):
    BACKGROUND = (15, 19, 29)          # Deep Void Slate (#0f131d)
    GRID_LINE = (30, 41, 59)           # Subtle Grid Blue-Slate (#1e293b)
    FOOD = (255, 80, 110)              # Target Hologram Crimson Pink (#ff506e)
    FOOD_GLOW = (255, 0, 85)           # Crimson Ruby halo (#ff0055)
    SNAKE_WALKING = (0, 255, 136)      # Electric Emerald Core (#00ff88)
    SNAKE_DEAD = (255, 0, 85)          # Hazard / Crimson Ruby (#ff0055)
    SNAKE_FULL = (245, 158, 11)        # Milestone Amber Gold (#f59e0b)
    HUD_BG = (10, 15, 24)              # HUD Background Slate (#0a0f18)
    HUD_CARD = (23, 28, 37)            # Surface Container Low (#171c25)
    HUD_BORDER = (48, 53, 63)          # Surface Container Highest (#30353f)
    TEXT_PRIMARY = (241, 255, 239)     # High-contrast White/Mint (#f1ffef)
    TEXT_MUTED = (148, 163, 184)       # Telemetry Grey (#94a3b8)
    ACCENT_AMBER = (245, 158, 11)      # Record / Milestone Gold (#f59e0b)
