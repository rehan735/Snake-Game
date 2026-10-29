import os

from src.cell import CellType
from src.direc import Direction
from src.pos import Pos


class Config:
    FPS: float = 60

    HUD_HEIGHT: int = 70
    SCREEN_SIZE: tuple[int, int] = (550, 550 + HUD_HEIGHT)
    GRID_SIZE: int = 10
    CELL_SIZE: float = 550.0 / GRID_SIZE
    CELL_PADDING: float = 6
    GRID_OFFSET_Y: int = HUD_HEIGHT

    MOVE_FREQ_START: int = 160    # initial speed in ms (comfortable start, not very slow)
    MOVE_FREQ_DEFAULT: int = 160  # default start ms per move
    MOVE_FREQ_MIN: int = 70       # max speed cap (normal arcade pace, not very fast)
    MOVE_FREQ_MAX: int = 240      # slowest allowed limit (prevents it being very slow)
    MOVE_FREQ_STEP: int = 15      # change per +/- key press
    MOVE_FREQ_ACCEL: float = 2.0  # ms faster per food eaten

    INIT_SNAKE_DIREC: Direction = Direction.RIGHT
    INIT_SNAKE_FOOD: Pos = Pos(8, 8)

    INIT_SNAKE_POS: list[Pos] = [
        Pos(1, 1),
        Pos(1, 2),
        Pos(1, 3),
    ]

    INIT_SNAKE_CELLS: list[CellType] = [
        CellType.BODY_HORZ,
        CellType.BODY_HORZ,
        CellType.HEAD_RIGHT,
    ]

    LOG_DIR: str = os.path.join(".", "logs")
    LOG_PFX: str = "SNAKE"
    STATES_EXT: str = ".txt"
    RECORD_EXT: str = ".gif"
