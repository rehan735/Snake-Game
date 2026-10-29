import math
import os
import time
from datetime import datetime, timezone

# pygame envs
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame
from PIL import Image

from src.agents import init_agent
from src.agents.base import Agent
from src.cell import CellColor, CellType
from src.cfg import Config
from src.direc import Direction
from src.mode import Mode
from src.pos import Pos
from src.snake import Snake


class Game:
    def __init__(
        self,
        mode: Mode,
        move_freq: int,
        show_grid: bool,
        record_frames: bool,
        rand_seed: int | None,
    ) -> None:
        self.mode: Mode = mode
        self.base_move_freq: int = move_freq
        self.move_freq: int = move_freq
        self.show_grid: bool = show_grid
        self.record_frames: bool = record_frames
        self.rand_seed: int | None = rand_seed
        self.agent: Agent | None = init_agent(self.mode)

        self.high_score: int = len(Config.INIT_SNAKE_POS)
        self.font_title: pygame.font.Font | None = None
        self.font_mono: pygame.font.Font | None = None
        self.font_bold: pygame.font.Font | None = None

        # Cached HUD surfaces – rebuilt on init and only when values change
        self._hud_static: pygame.Surface | None = None  # background + static labels
        self._hud_score_surf: pygame.Surface | None = None  # score number (changes on eat)
        self._hud_record_surf: pygame.Surface | None = None  # high score number
        self._hud_status_surf: pygame.Surface | None = None  # speed / PAUSED / OVER tag
        self._hud_score_val: int = -1      # last rendered score value
        self._hud_record_val: int = -1     # last rendered high-score value
        self._hud_status_key: str = ""     # last rendered status string
        self._hud_score_x: int = 190       # x position of PTS label (depends on score width)
        self._tongue_until: float = 0.0     # monotonic time until tongue is visible

        self.snake: Snake
        self.paused: bool
        self.last_move_time: float
        self.next_direc: Direction | None
        self.log_path_pfx: str
        self.frames: list[Image.Image]
        self.reset()

        self.screen: pygame.Surface

    def reset(self) -> None:
        self.snake = Snake(
            Config.GRID_SIZE,
            Config.INIT_SNAKE_POS,
            Config.INIT_SNAKE_CELLS,
            Config.INIT_SNAKE_DIREC,
            Config.INIT_SNAKE_FOOD,
            self.rand_seed,
        )
        self.paused = False
        self.last_move_time = time.monotonic()
        self.next_direc = None
        self.move_freq = self.base_move_freq
        self._hud_status_key = ""
        self.log_path_pfx = self.init_logging()
        self.frames = []

    def _update_speed(self) -> None:
        food_eaten = max(0, self.snake.len() - len(Config.INIT_SNAKE_POS))
        target_freq = int(self.base_move_freq - food_eaten * Config.MOVE_FREQ_ACCEL)
        self.move_freq = max(Config.MOVE_FREQ_MIN, min(Config.MOVE_FREQ_MAX, target_freq))
        self._hud_status_key = ""

    def init_logging(self) -> str:
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
        pfx = os.path.join(Config.LOG_DIR, f"{Config.LOG_PFX}_{self.mode.name}_{ts}")
        with open(pfx + Config.STATES_EXT, "w") as f:
            f.write(f"Random seed for food generation: {self.snake.rand_seed}\n")
            f.write("-" * (Config.GRID_SIZE * 3) + "\n")
        return pfx

    def print_info(self) -> None:
        print("+----------------------------------+")
        print("| Esc    : Quit the game           |")
        print("| Space  : Pause/Resume the game   |")
        print("| R      : Restart the game        |")
        print("| W/A/S/D: Move the snake          |")
        print("| -      : Slow down snake         |")
        print("| +      : Speed up snake          |")
        print("+----------------------------------+")
        print(f"Game started in {self.mode.name} mode. {self.mode.value}")

    def print_score(self) -> None:
        print(
            f"Score: {self.snake.len():>2} (length of the snake, max={Config.GRID_SIZE**2})"
        )

    def loop(self) -> None:
        self.print_info()

        pygame.init()
        pygame.font.init()
        try:
            self.font_title = pygame.font.SysFont("segoeui,helvetica,arial", 12, bold=True)
            self.font_mono = pygame.font.SysFont("consolas,monospace", 10)
            self.font_bold = pygame.font.SysFont("segoeui,helvetica,arial", 17, bold=True)
        except Exception:
            self.font_title = pygame.font.Font(None, 16)
            self.font_mono = pygame.font.Font(None, 14)
            self.font_bold = pygame.font.Font(None, 22)

        self.screen = pygame.display.set_mode(Config.SCREEN_SIZE, pygame.NOFRAME)
        self._rebuild_hud_cache()  # pre-render all static text surfaces once
        clock = pygame.time.Clock()

        while True:
            if not self.handle_events():
                break
            self.move()
            self.refresh_screen()
            self.capture_frame()
            clock.tick(Config.FPS)

        self.save_recording()
        pygame.quit()

    def handle_events(self) -> bool:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_r:
                    self.save_recording()
                    self.reset()
                elif event.key == pygame.K_MINUS:
                    self.base_move_freq = min(self.base_move_freq + Config.MOVE_FREQ_STEP, Config.MOVE_FREQ_MAX)
                    self._update_speed()
                    print(f"Speed: {self.move_freq}ms/move")
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    self.base_move_freq = max(self.base_move_freq - Config.MOVE_FREQ_STEP, Config.MOVE_FREQ_MIN)
                    self._update_speed()
                    print(f"Speed: {self.move_freq}ms/move")
                elif event.key == pygame.K_w:
                    self.next_direc = Direction.UP
                elif event.key == pygame.K_a:
                    self.next_direc = Direction.LEFT
                elif event.key == pygame.K_s:
                    self.next_direc = Direction.DOWN
                elif event.key == pygame.K_d:
                    self.next_direc = Direction.RIGHT
        return True

    def move(self) -> None:
        now = time.monotonic()
        if (now - self.last_move_time) * 1000 < self.move_freq:
            return

        self.last_move_time = now

        if self.game_over():
            return

        if not self.next_direc_valid():
            if self.paused:
                self.next_direc = None
            elif self.agent:
                self.next_direc = self.agent.next_direc(self.snake)
            else:
                self.next_direc = self.snake.direc
            if not self.next_direc_valid():
                return

        assert self.next_direc is not None
        old_len = self.snake.len()
        self.snake.move(self.next_direc)
        self.next_direc = None
        new_len = self.snake.len()
        if new_len != old_len:
            self.high_score = max(self.high_score, new_len)
            self._hud_score_val = -1   # invalidate cached score surface
            self._hud_record_val = -1  # invalidate high-score surface
            self._tongue_until = time.monotonic() + 0.6  # show tongue for 0.6 s after eating
            self._update_speed()
        self.save_states()

        if self.game_over():
            self.print_score()

    def game_over(self) -> bool:
        return self.snake.is_stopped()

    def next_direc_valid(self) -> bool:
        # fmt: off
        return (
            self.next_direc is not None
            and not self.snake.direc.is_opposite(self.next_direc)
        )
        # fmt: on

    def refresh_screen(self) -> None:
        self.screen.fill(CellColor.BACKGROUND.value)

        self.draw_hud()
        self.draw_arena_frame()

        if self.show_grid:
            self.draw_grid()

        if self.snake.food:
            self.draw_food(self.snake.food)

        self.draw_snake()

        pygame.display.flip()

    def _rebuild_hud_cache(self) -> None:
        """Pre-render all static HUD label surfaces once. Called on init and font change."""
        w = Config.SCREEN_SIZE[0]
        h = Config.HUD_HEIGHT
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill(CellColor.HUD_BG.value)

        # Hairline bottom border
        pygame.draw.line(surf, CellColor.HUD_BORDER.value, (0, h - 1), (w, h - 1), 1)

        # Card 1 background
        c1 = pygame.Rect(10, 10, 160, 50)
        pygame.draw.rect(surf, CellColor.HUD_CARD.value, c1, border_radius=6)
        pygame.draw.rect(surf, CellColor.HUD_BORDER.value, c1, width=1, border_radius=6)

        # Card 2 background
        c2 = pygame.Rect(180, 10, 185, 50)
        pygame.draw.rect(surf, CellColor.HUD_CARD.value, c2, border_radius=6)
        pygame.draw.rect(surf, (0, 100, 60), c2, width=1, border_radius=6)

        # Card 3 background
        c3 = pygame.Rect(375, 10, 165, 50)
        pygame.draw.rect(surf, CellColor.HUD_CARD.value, c3, border_radius=6)
        pygame.draw.rect(surf, CellColor.HUD_BORDER.value, c3, width=1, border_radius=6)

        # Card 1 static labels
        if self.font_title:
            s = self.font_title.render("CYBER SNAKE", True, CellColor.TEXT_PRIMARY.value)
            surf.blit(s, (32, 17))
        if self.font_mono:
            s = self.font_mono.render(f"10x10 // {self.mode.name}", True, CellColor.TEXT_MUTED.value)
            surf.blit(s, (20, 36))

        # Card 2 static labels
        if self.font_mono:
            s = self.font_mono.render("ACTIVE SCORE", True, CellColor.TEXT_MUTED.value)
            surf.blit(s, (190, 16))
            s = self.font_mono.render("+1 CIRCLE", True, CellColor.SNAKE_WALKING.value)
            surf.blit(s, (295, 16))
            s = self.font_mono.render("PTS", True, (0, 220, 120))
            surf.blit(s, (220, 33))   # approximate; refined each score update

        # Card 3 static labels
        if self.font_mono:
            s = self.font_mono.render("SECTOR RECORD", True, CellColor.TEXT_MUTED.value)
            surf.blit(s, (385, 16))
            s = self.font_mono.render("MAX", True, (200, 140, 20))
            surf.blit(s, (420, 33))   # approximate; refined each record update

        # Progress bar background (static)
        bar_bg = pygame.Rect(190, 48, 165, 3)
        pygame.draw.rect(surf, CellColor.HUD_BORDER.value, bar_bg, border_radius=2)

        self._hud_static = surf
        # Invalidate dynamic caches so they're redrawn next frame
        self._hud_score_val = -1
        self._hud_record_val = -1
        self._hud_status_key = ""

    def _refresh_hud_dynamic(self) -> None:
        """Render only HUD surfaces whose value has changed since last frame."""
        score = self.snake.len()
        if score != self._hud_score_val and self.font_bold:
            self._hud_score_surf = self.font_bold.render(
                str(score), True, CellColor.SNAKE_WALKING.value
            )
            self._hud_score_val = score

        record = self.high_score
        if record != self._hud_record_val and self.font_bold:
            self._hud_record_surf = self.font_bold.render(
                str(record), True, CellColor.ACCENT_AMBER.value
            )
            self._hud_record_val = record

        if self.paused:
            key = "PAUSED"
        elif self.game_over():
            key = "OVER"
        else:
            key = f"{self.move_freq}ms"
        if key != self._hud_status_key and self.font_mono:
            color = CellColor.FOOD.value if key in ("PAUSED", "OVER") else CellColor.TEXT_MUTED.value
            self._hud_status_surf = self.font_mono.render(key, True, color)
            self._hud_status_key = key

    def draw_hud(self) -> None:
        now = time.monotonic()

        # Blit pre-rendered static layer
        if self._hud_static:
            self.screen.blit(self._hud_static, (0, 0))

        # Refresh only changed dynamic surfaces
        self._refresh_hud_dynamic()

        # Pulsing live LED dot (animates each frame, no text render)
        pulse_alpha = (math.sin(now * 6) + 1) / 2
        led_color = (0, int(200 + 55 * pulse_alpha), int(100 + 36 * pulse_alpha))
        pygame.draw.circle(self.screen, led_color, (22, 25), 3)
        if pulse_alpha > 0.4:
            pygame.draw.circle(self.screen, (0, 255, 136), (22, 25), 5, width=1)

        # Blit cached score value
        if self._hud_score_surf:
            self.screen.blit(self._hud_score_surf, (190, 27))

        # Score progress bar fill (cheap rect, value changes rarely)
        score = self.snake.len()
        pct = min(1.0, score / (Config.GRID_SIZE ** 2))
        if pct > 0:
            bar_fill = pygame.Rect(190, 48, int(165 * pct), 3)
            pygame.draw.rect(self.screen, CellColor.SNAKE_WALKING.value, bar_fill, border_radius=2)

        # Blit cached high score value
        if self._hud_record_surf:
            self.screen.blit(self._hud_record_surf, (385, 27))

        # Blit cached status tag
        if self._hud_status_surf:
            self.screen.blit(self._hud_status_surf, (495, 33))

    def draw_arena_frame(self) -> None:
        # Subtle tactical corner vector brackets on the 4 corners of the 10x10 grid floor
        off_y = Config.GRID_OFFSET_Y
        w = Config.SCREEN_SIZE[0]
        h = Config.SCREEN_SIZE[1] - off_y
        col = (0, 255, 136)
        arm = 12

        # Top-left corner bracket
        pygame.draw.line(self.screen, col, (4, off_y + 4), (4 + arm, off_y + 4), 2)
        pygame.draw.line(self.screen, col, (4, off_y + 4), (4, off_y + 4 + arm), 2)

        # Top-right corner bracket
        pygame.draw.line(self.screen, col, (w - 5, off_y + 4), (w - 5 - arm, off_y + 4), 2)
        pygame.draw.line(self.screen, col, (w - 5, off_y + 4), (w - 5, off_y + 4 + arm), 2)

        # Bottom-left corner bracket
        pygame.draw.line(self.screen, col, (4, off_y + h - 5), (4 + arm, off_y + h - 5), 2)
        pygame.draw.line(self.screen, col, (4, off_y + h - 5), (4, off_y + h - 5 - arm), 2)

        # Bottom-right corner bracket
        pygame.draw.line(self.screen, col, (w - 5, off_y + h - 5), (w - 5 - arm, off_y + h - 5), 2)
        pygame.draw.line(self.screen, col, (w - 5, off_y + h - 5), (w - 5, off_y + h - 5 - arm), 2)

    def draw_grid(self) -> None:
        off_y = Config.GRID_OFFSET_Y
        for row in range(Config.GRID_SIZE):
            for col in range(Config.GRID_SIZE):
                x = col * Config.CELL_SIZE
                y = off_y + row * Config.CELL_SIZE
                w = h = Config.CELL_SIZE
                pygame.draw.rect(self.screen, CellColor.GRID_LINE.value, (x, y, w, h), 1)

    def draw(self, pos: Pos, cell_type: CellType) -> None:
        if cell_type == CellType.EMPTY:
            self.draw_empty(pos)
        elif cell_type == CellType.FOOD:
            self.draw_food(pos)
        else:
            coords = list(self.snake.coords)
            total = len(coords)
            idx = total - 1
            if pos in coords:
                idx = coords.index(pos)
            is_dead = self.snake.state == Snake.State.DEAD
            is_full = self.snake.state == Snake.State.FULL
            t = idx / max(total - 1, 1)
            head_r = int(Config.CELL_SIZE / 2 + 2)
            tail_r = int(Config.CELL_SIZE / 2 - 6)
            radius = int(tail_r + (head_r - tail_r) * t)
            self.draw_snake_segment(pos, idx, total, radius, is_dead, is_full)

    def draw_empty(self, pos: Pos) -> None:
        row, col = pos.row, pos.col
        x = col * Config.CELL_SIZE
        y = Config.GRID_OFFSET_Y + row * Config.CELL_SIZE
        w = h = Config.CELL_SIZE
        pygame.draw.rect(self.screen, CellColor.BACKGROUND.value, (x, y, w, h))
        if self.show_grid:
            pygame.draw.rect(self.screen, CellColor.GRID_LINE.value, (x, y, w, h), 1)

    def draw_food(self, pos: Pos) -> None:
        row, col = pos.row, pos.col
        cx = int(col * Config.CELL_SIZE + Config.CELL_SIZE / 2)
        cy = int(Config.GRID_OFFSET_Y + row * Config.CELL_SIZE + Config.CELL_SIZE / 2)

        base_r = int((Config.CELL_SIZE - 2 * Config.CELL_PADDING) / 2)

        # Blinking cycle: ~2.8 blinks/sec
        now = time.monotonic()
        blink_period = 0.35
        phase = (now % blink_period) / blink_period
        is_bright = phase < 0.70

        if is_bright:
            # Pulsing radius
            pulse = math.sin(now * 8) * 1.5
            r = max(4, int(base_r + pulse))

            # Expanding holographic ping aura ring (Target Hologram Apple from Stitch)
            ping_phase = (now * 2.0) % 1.0
            ping_r = int(r + ping_phase * 7)
            ping_col = (255, 0, 85)
            pygame.draw.circle(self.screen, ping_col, (cx, cy), ping_r, width=1)

            # Outer glowing halo
            glow_color = (255, 60, 100)
            pygame.draw.circle(self.screen, glow_color, (cx, cy), r + 2, width=2)

            # Main food circle (Target Crimson Ruby)
            food_color = CellColor.FOOD.value
            pygame.draw.circle(self.screen, food_color, (cx, cy), r)

            # Outer border ring
            border_color = CellColor.FOOD_GLOW.value
            pygame.draw.circle(self.screen, border_color, (cx, cy), r, width=2)

            # 3D specular shine (pure white gleam)
            shine_r = max(2, int(r * 0.30))
            shine_x = cx - int(r * 0.28)
            shine_y = cy - int(r * 0.28)
            pygame.draw.circle(self.screen, (255, 255, 255), (shine_x, shine_y), shine_r)
        else:
            # Dimmed / blinking off state (faint tactical target reticle)
            dim_color = (90, 25, 45)
            pygame.draw.circle(self.screen, dim_color, (cx, cy), max(3, base_r - 2), width=1)
            pygame.draw.circle(self.screen, (140, 40, 60), (cx, cy), 2)

    def get_color_palette(
        self, base: tuple[int, int, int]
    ) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
        r, g, b = base
        highlight = (
            min(255, int(r * 0.70 + 255 * 0.30)),
            min(255, int(g * 0.70 + 255 * 0.30)),
            min(255, int(b * 0.70 + 255 * 0.30)),
        )
        connector = (
            max(0, int(r * 0.85)),
            max(0, int(g * 0.85)),
            max(0, int(b * 0.85)),
        )
        shadow = (
            max(0, int(r * 0.35)),
            max(0, int(g * 0.35)),
            max(0, int(b * 0.35)),
        )
        return base, highlight, connector, shadow

    def _slither_segment_color(self, index: int, total: int, is_dead: bool, is_full: bool) -> tuple[int, int, int]:
        """Return the Slither.io-style gradient color for a snake segment.

        index 0 = tail (darkest green), index total-1 = head (tan/beige).
        """
        if is_dead:
            # Desaturated red gradient tail→head
            t = index / max(total - 1, 1)
            r = int(80 + 120 * t)
            g = int(20 + 20 * t)
            b = int(20 + 20 * t)
            return (r, g, b)
        if is_full:
            # Amber/gold gradient
            t = index / max(total - 1, 1)
            r = int(120 + 125 * t)
            g = int(80 + 78 * t)
            b = int(0)
            return (r, g, b)

        # Normal walking: dark green tail → light green body → tan head
        t = index / max(total - 1, 1)  # 0.0 at tail, 1.0 at head
        is_head = (index == total - 1)
        if is_head:
            # Tan / beige head like in the reference image
            return (200, 190, 120)
        # Body: dark forest green at tail → medium bright green toward neck
        r = int(40 + 60 * t)     # 40 → 100
        g = int(100 + 100 * t)   # 100 → 200
        b = int(30 + 20 * t)     # 30 → 50
        return (r, g, b)

    def draw_snake(self) -> None:
        coords = list(self.snake.coords)
        if not coords:
            return

        is_dead = self.snake.state == Snake.State.DEAD
        is_full = self.snake.state == Snake.State.FULL
        total = len(coords)

        # All radii > CELL_SIZE/2 so adjacent circles (centers are CELL_SIZE apart)
        # always overlap and naturally join — no connector lines needed.
        head_radius = int(Config.CELL_SIZE / 2 + 8)
        tail_radius = int(Config.CELL_SIZE / 2 + 2)

        def seg_radius(i: int) -> int:
            t = i / max(total - 1, 1)
            return int(tail_radius + (head_radius - tail_radius) * t)

        # Draw tail → head so each larger circle overlaps onto the previous one
        for i, pos in enumerate(coords):
            self.draw_snake_segment(pos, i, total, seg_radius(i), is_dead, is_full)

    def draw_snake_segment(
        self,
        pos: Pos,
        index: int,
        total: int,
        radius: int,
        is_dead: bool,
        is_full: bool,
    ) -> None:
        if self.snake.is_out_of_bound(pos):
            return

        cx = int(pos.col * Config.CELL_SIZE + Config.CELL_SIZE / 2)
        cy = int(Config.GRID_OFFSET_Y + pos.row * Config.CELL_SIZE + Config.CELL_SIZE / 2)
        is_head = (index == total - 1)

        seg_color = self._slither_segment_color(index, total, is_dead, is_full)

        # Slightly darker outline for depth
        outline = (
            max(0, seg_color[0] - 30),
            max(0, seg_color[1] - 40),
            max(0, seg_color[2] - 10),
        )
        pygame.draw.circle(self.screen, outline, (cx, cy), radius)
        pygame.draw.circle(self.screen, seg_color, (cx, cy), radius - 2)

        if is_head:
            self.draw_snake_eyes(cx, cy, radius)
            self.draw_snake_tongue(cx, cy, radius)

    def draw_snake_tongue(self, cx: int, cy: int, radius: int) -> None:
        """Draw a forked red tongue — only visible for a short window after eating."""
        if time.monotonic() > self._tongue_until:
            return
        if self.snake.state == Snake.State.DEAD:
            return
        direc = self.snake.direc
        tongue_len = int(radius * 1.1)
        fork_len = int(radius * 0.45)
        fork_spread = int(radius * 0.30)
        tongue_color = (220, 40, 40)
        lw = max(1, int(radius * 0.10))

        # Base of tongue: starts at edge of head circle
        if direc == Direction.RIGHT:
            bx, by = cx + radius - 2, cy
            ex, ey = bx + tongue_len, by
            pygame.draw.line(self.screen, tongue_color, (bx, by), (ex, ey), lw)
            pygame.draw.line(self.screen, tongue_color, (ex, ey), (ex + fork_len, ey - fork_spread), lw)
            pygame.draw.line(self.screen, tongue_color, (ex, ey), (ex + fork_len, ey + fork_spread), lw)
        elif direc == Direction.LEFT:
            bx, by = cx - radius + 2, cy
            ex, ey = bx - tongue_len, by
            pygame.draw.line(self.screen, tongue_color, (bx, by), (ex, ey), lw)
            pygame.draw.line(self.screen, tongue_color, (ex, ey), (ex - fork_len, ey - fork_spread), lw)
            pygame.draw.line(self.screen, tongue_color, (ex, ey), (ex - fork_len, ey + fork_spread), lw)
        elif direc == Direction.UP:
            bx, by = cx, cy - radius + 2
            ex, ey = bx, by - tongue_len
            pygame.draw.line(self.screen, tongue_color, (bx, by), (ex, ey), lw)
            pygame.draw.line(self.screen, tongue_color, (ex, ey), (ex - fork_spread, ey - fork_len), lw)
            pygame.draw.line(self.screen, tongue_color, (ex, ey), (ex + fork_spread, ey - fork_len), lw)
        else:  # DOWN
            bx, by = cx, cy + radius - 2
            ex, ey = bx, by + tongue_len
            pygame.draw.line(self.screen, tongue_color, (bx, by), (ex, ey), lw)
            pygame.draw.line(self.screen, tongue_color, (ex, ey), (ex - fork_spread, ey + fork_len), lw)
            pygame.draw.line(self.screen, tongue_color, (ex, ey), (ex + fork_spread, ey + fork_len), lw)

    def draw_snake_eyes(self, cx: int, cy: int, radius: int) -> None:
        direc = self.snake.direc
        # Slither.io style: large dark eyes, no white sclera
        eye_r = max(3, int(radius * 0.28))
        pupil_r = max(2, int(radius * 0.16))

        if direc == Direction.RIGHT:
            e1 = (cx + int(radius * 0.22), cy - int(radius * 0.38))
            e2 = (cx + int(radius * 0.22), cy + int(radius * 0.38))
        elif direc == Direction.LEFT:
            e1 = (cx - int(radius * 0.22), cy - int(radius * 0.38))
            e2 = (cx - int(radius * 0.22), cy + int(radius * 0.38))
        elif direc == Direction.UP:
            e1 = (cx - int(radius * 0.38), cy - int(radius * 0.22))
            e2 = (cx + int(radius * 0.38), cy - int(radius * 0.22))
        else:  # Direction.DOWN
            e1 = (cx - int(radius * 0.38), cy + int(radius * 0.22))
            e2 = (cx + int(radius * 0.38), cy + int(radius * 0.22))

        for eye_center in (e1, e2):
            if self.snake.state == Snake.State.DEAD:
                sz = max(2, eye_r - 1)
                x0, y0 = eye_center
                pygame.draw.line(self.screen, (200, 0, 0), (x0 - sz, y0 - sz), (x0 + sz, y0 + sz), 2)
                pygame.draw.line(self.screen, (200, 0, 0), (x0 - sz, y0 + sz), (x0 + sz, y0 - sz), 2)
            else:
                # Dark eye base (like reference image — no white, just dark circle)
                pygame.draw.circle(self.screen, (20, 20, 20), eye_center, eye_r)
                # Small white gleam
                gleam = (eye_center[0] - max(1, eye_r // 3), eye_center[1] - max(1, eye_r // 3))
                pygame.draw.circle(self.screen, (220, 220, 220), gleam, max(1, pupil_r - 1))

    def snake_color(self) -> tuple[int, int, int]:
        """Returns the base snake color (used by legacy draw() call path)."""
        if self.snake.state == Snake.State.WALKING:
            return CellColor.SNAKE_WALKING.value
        if self.snake.state == Snake.State.DEAD:
            return CellColor.SNAKE_DEAD.value
        if self.snake.state == Snake.State.FULL:
            return CellColor.SNAKE_FULL.value
        assert False, f"Unexpected snake state {self.snake.state.name}"

    def capture_frame(self) -> None:
        if not self.record_frames:
            return
        data = pygame.image.tobytes(self.screen, "RGB")
        size = self.screen.get_size()
        self.frames.append(Image.frombytes("RGB", size, data))

    def save_recording(self) -> None:
        if not self.record_frames or not self.frames:
            return
        self.frames[0].save(
            self.log_path_pfx + Config.RECORD_EXT,
            save_all=True,
            append_images=self.frames[1:],
            duration=int(1000 / Config.FPS),
            loop=0,
        )

    def save_states(self) -> None:
        with open(self.log_path_pfx + Config.STATES_EXT, "a") as f:
            f.write(self.snake.serialize_states() + "\n")
