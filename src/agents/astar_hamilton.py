
from __future__ import annotations

import heapq
from collections import deque

from src.agents.base import Agent
from src.direc import Direction
from src.pos import Pos
from src.snake import Snake


class AStarHamiltonAgent(Agent):
    """
    Snake agent prioritizing the shortest A* path to food, backed by tail-path
    simulation and Hamiltonian cycle fallbacks to guarantee high score.
    """

    def __init__(self) -> None:
        self.snake: Snake | None = None
        self.cycle_order: list[list[int]] = []
        self.cycle_size: int = 0

    def reset(self, snake: Snake | None = None) -> None:
        self.snake = snake
        if snake is not None:
            self._init_for_snake(snake)

    def next_direc(self, snake: Snake) -> Direction:
        if self.snake is not snake or not self.cycle_order:
            self._init_for_snake(snake)

        food = snake.food
        assert food is not None
        head = snake.head()

        # ── 1. Shortest Path to Food (A*) ────────────────────────────────────
        path_to_food = self._astar(food, snake)
        if path_to_food:
            sim = snake.copy()
            for d in path_to_food:
                sim.move(d)

            # If this path completes the game, take it immediately!
            if sim.max_len_reached() or sim.state == Snake.State.FULL:
                return path_to_food[0]

            # After eating food, verify that the snake can still reach its tail
            path_to_tail = self._astar(sim.tail(), sim)
            if path_to_tail:
                # Safe to take the shortest path directly to reward!
                return path_to_food[0]

        # ── 2. Safe Stalling: Longer Path to Tail ──────────────────────────────
        path_to_tail = self._longer_path(snake.tail(), snake)
        if path_to_tail:
            return path_to_tail[0]

        # ── 3. Fallback: Shortest Path to Tail (A*) ───────────────────────────
        path_to_tail = self._astar(snake.tail(), snake)
        if path_to_tail:
            return path_to_tail[0]

        # ── 4. Fallback: Neighbor with Maximum Connected Free Space ───────────
        best_space = -1
        best_d: Direction | None = None
        for direc in Direction:
            nbr = head.adj(direc)
            if not snake.is_out_of_bound(nbr) and (
                snake.is_empty(nbr) or snake.is_tail(nbr)
            ):
                sp = self._flood_fill(nbr, snake)
                if sp > best_space:
                    best_space = sp
                    best_d = direc

        if best_d is not None:
            return best_d

        # ── 5. Ultimate Fallback: Hamiltonian Cycle or Current Heading ────────
        h_idx = self.cycle_order[head.row][head.col]
        target_step = (h_idx + 1) % self.cycle_size
        for direc in Direction:
            nbr = head.adj(direc)
            if (
                not snake.is_out_of_bound(nbr)
                and self.cycle_order[nbr.row][nbr.col] == target_step
            ):
                return direc

        return snake.direc

    # ────────────────────────────── A* Search ─────────────────────────────────

    def _astar(self, dst: Pos, snake: Snake) -> list[Direction]:
        """Find the shortest path from snake head to dst using A* search."""
        src = snake.head()
        if src == dst:
            return []

        heap: list[tuple[int, int, int, Pos, list[Direction]]] = []
        counter = 0
        heapq.heappush(heap, (self._manhattan(src, dst), counter, 0, src, []))
        visited: set[Pos] = {src}

        while heap:
            _f, _c, g, cur, path = heapq.heappop(heap)
            if cur == dst:
                return path

            for direc in Direction:
                nbr = cur.adj(direc)
                if snake.is_out_of_bound(nbr) or nbr in visited:
                    continue
                # Moving into tail is valid as long as it's not food
                if snake.is_snake(nbr) and not (
                    snake.is_tail(nbr) and not snake.is_food(nbr)
                ):
                    continue

                visited.add(nbr)
                counter += 1
                ng = g + 1
                nf = ng + self._manhattan(nbr, dst)
                heapq.heappush(heap, (nf, counter, ng, nbr, path + [direc]))

        return []

    # ───────────────────────────── Longer Path ────────────────────────────────

    def _longer_path(self, dst: Pos, snake: Snake) -> list[Direction]:
        """Construct a path longer than shortest path via perpendicular zig-zags."""
        shortest = self._astar(dst, snake)
        if not shortest:
            return []

        longest: list[Direction] = []
        cur = snake.head()

        for direc in shortest:
            nxt = cur.adj(direc)
            extended = False
            perps = (
                [Direction.LEFT, Direction.RIGHT]
                if direc in (Direction.UP, Direction.DOWN)
                else [Direction.UP, Direction.DOWN]
            )

            for td in perps:
                c_ext = cur.adj(td)
                n_ext = nxt.adj(td)
                c_ok = (
                    not snake.is_out_of_bound(c_ext)
                    and (snake.is_empty(c_ext) or snake.is_tail(c_ext))
                    and not snake.is_food(c_ext)
                )
                n_ok = not snake.is_out_of_bound(n_ext) and (
                    snake.is_empty(n_ext)
                    or snake.is_tail(n_ext)
                    or n_ext == snake.coords[1]
                )
                if c_ok and n_ok:
                    longest.extend([td, direc, td.opposite()])
                    extended = True
                    break

            if not extended:
                longest.append(direc)

            cur = nxt

        return longest

    # ──────────────────────────── Free Space (BFS) ───────────────────────────

    def _flood_fill(self, start: Pos, snake: Snake) -> int:
        """Count the number of connected empty cells reachable from start."""
        visited: set[Pos] = {start}
        queue: deque[Pos] = deque([start])

        while queue:
            cur = queue.popleft()
            for direc in Direction:
                nbr = cur.adj(direc)
                if (
                    not snake.is_out_of_bound(nbr)
                    and not snake.is_snake(nbr)
                    and nbr not in visited
                ):
                    visited.add(nbr)
                    queue.append(nbr)

        return len(visited)

    # ───────────────────────── Hamiltonian Cycle ──────────────────────────────

    def _build_cycle(self, n: int) -> list[list[int]]:
        """Pre-compute a boustrophedon closed cycle for n x n grid."""
        order: list[list[int]] = [[0] * n for _ in range(n)]
        step = 0
        for row in range(n):
            col_range = range(1, n) if row % 2 == 0 else range(n - 1, 0, -1)
            for col in col_range:
                order[row][col] = step
                step += 1
        for row in range(n - 1, -1, -1):
            order[row][0] = step
            step += 1

        total = n * n
        return [[(total - 1 - order[r][c]) for c in range(n)] for r in range(n)]

    def _init_for_snake(self, snake: Snake) -> None:
        self.snake = snake
        n = snake.grid_size
        self.cycle_order = self._build_cycle(n)
        self.cycle_size = n * n

    def _manhattan(self, p1: Pos, p2: Pos) -> int:
        return abs(p1.row - p2.row) + abs(p1.col - p2.col)
