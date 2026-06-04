#!/usr/bin/env python3
"""Terminal UI for entering and solving a Sudoku puzzle.

Run:
    python3 sudoku_tui.py
"""

from __future__ import annotations

import curses
from dataclasses import dataclass
from pathlib import Path

from sudoku_solver import GRID_WIDTH, format_grid, iter_solutions, validate_givens


BOARD_SIZE = GRID_WIDTH * GRID_WIDTH
GRID_TOP = 2
GRID_LEFT = 2
BUTTON_ROW = GRID_TOP + 13
BUTTON_LEFT = GRID_LEFT
RESULT_TOP = GRID_TOP
RESULT_LEFT = GRID_LEFT + 31
MIN_HEIGHT = 24
MIN_WIDTH = 64
OUTPUT_PATH = Path("sudoku_solutions.txt")


@dataclass
class AppState:
    cells: list[str]
    row: int = 0
    col: int = 0
    focus: str = "grid"
    status: str = "Enter digits, then resolve."
    result_count: int | None = None
    first_solution: str | None = None
    output_path: str | None = None


def grid_string(cells: list[str]) -> str:
    return "".join(cell if cell else "0" for cell in cells)


def cell_position(row: int, col: int) -> tuple[int, int]:
    y = GRID_TOP + 1 + row + row // 3
    x = GRID_LEFT + 2 + (col * 2) + ((col // 3) * 2)
    return y, x


def add_text(stdscr: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = stdscr.getmaxyx()
    if 0 <= y < height and x < width:
        stdscr.addnstr(y, x, text, max(0, width - x - 1), attr)


def draw_grid(stdscr: curses.window, state: AppState) -> None:
    border = "+-------+-------+-------+"
    row_template = "| . . . | . . . | . . . |"

    for row in range(GRID_WIDTH):
        if row % 3 == 0:
            add_text(stdscr, GRID_TOP + row + row // 3, GRID_LEFT, border)

        y = GRID_TOP + 1 + row + row // 3
        add_text(stdscr, y, GRID_LEFT, row_template)
        for col in range(GRID_WIDTH):
            value = state.cells[row * GRID_WIDTH + col] or "."
            attr = (
                curses.A_REVERSE
                if state.focus == "grid" and row == state.row and col == state.col
                else 0
            )
            cell_y, cell_x = cell_position(row, col)
            add_text(stdscr, cell_y, cell_x, value, attr)

    add_text(stdscr, GRID_TOP + 12, GRID_LEFT, border)


def draw_first_solution(stdscr: curses.window, solution: str, top: int, left: int) -> None:
    for offset, line in enumerate(format_grid(solution).splitlines()):
        add_text(stdscr, top + offset, left, line)

    add_text(stdscr, top + 14, left, "String:")
    for offset in range(0, len(solution), 27):
        add_text(stdscr, top + 15 + (offset // 27), left, solution[offset : offset + 27])


def draw(stdscr: curses.window, state: AppState) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    if height < MIN_HEIGHT or width < MIN_WIDTH:
        add_text(
            stdscr,
            0,
            0,
            f"Terminal too small. Need at least {MIN_WIDTH}x{MIN_HEIGHT}.",
            curses.A_BOLD,
        )
        stdscr.refresh()
        return

    add_text(stdscr, 0, GRID_LEFT, "Sudoku TUI", curses.A_BOLD)
    add_text(stdscr, 0, 18, "Arrows move  1-9 enter  Del clears  Enter resolves  q quits")

    draw_grid(stdscr, state)

    button_attr = curses.A_REVERSE if state.focus == "button" else curses.A_BOLD
    add_text(stdscr, BUTTON_ROW, BUTTON_LEFT, "[ Resolve ]", button_attr)
    add_text(stdscr, BUTTON_ROW, BUTTON_LEFT + 14, state.status)

    if state.result_count is not None:
        plural = "solution" if state.result_count == 1 else "solutions"
        add_text(
            stdscr,
            RESULT_TOP,
            RESULT_LEFT,
            f"Found {state.result_count} {plural}.",
            curses.A_BOLD,
        )
        if state.first_solution:
            add_text(stdscr, RESULT_TOP + 2, RESULT_LEFT, "First solution:")
            draw_first_solution(stdscr, state.first_solution, RESULT_TOP + 3, RESULT_LEFT)
        else:
            add_text(stdscr, RESULT_TOP + 2, RESULT_LEFT, "No first solution available.")

        if state.output_path:
            add_text(stdscr, BUTTON_ROW + 1, BUTTON_LEFT, f"File: {state.output_path}")

    stdscr.refresh()


def move_cursor(state: AppState, key: int) -> None:
    if state.focus == "button":
        if key == curses.KEY_UP:
            state.focus = "grid"
            state.row = GRID_WIDTH - 1
        return

    if key == curses.KEY_UP:
        state.row = max(0, state.row - 1)
    elif key == curses.KEY_DOWN:
        if state.row == GRID_WIDTH - 1:
            state.focus = "button"
        else:
            state.row += 1
    elif key == curses.KEY_LEFT:
        state.col = max(0, state.col - 1)
    elif key == curses.KEY_RIGHT:
        state.col = min(GRID_WIDTH - 1, state.col + 1)


def clear_current_cell(state: AppState) -> None:
    if state.focus == "grid":
        state.cells[state.row * GRID_WIDTH + state.col] = ""
        state.status = "Cell cleared."
        state.result_count = None
        state.first_solution = None
        state.output_path = None


def set_current_cell(state: AppState, digit: str) -> None:
    if state.focus != "grid":
        return

    state.cells[state.row * GRID_WIDTH + state.col] = digit
    state.status = f"Set row {state.row + 1}, column {state.col + 1}."
    state.result_count = None
    state.first_solution = None
    state.output_path = None

    if state.col < GRID_WIDTH - 1:
        state.col += 1
    elif state.row < GRID_WIDTH - 1:
        state.row += 1
        state.col = 0
    else:
        state.focus = "button"


def resolve_current_grid(stdscr: curses.window, state: AppState) -> None:
    grid = grid_string(state.cells)
    state.result_count = 0
    state.first_solution = None
    state.output_path = None

    try:
        validate_givens(grid)
    except ValueError as exc:
        state.result_count = None
        state.status = f"Invalid puzzle: {exc}"
        return

    try:
        output_file = OUTPUT_PATH.open("w", encoding="utf-8")
    except OSError as exc:
        state.result_count = None
        state.status = f"Could not open {OUTPUT_PATH}: {exc}"
        return

    state.output_path = str(OUTPUT_PATH)
    state.status = f"Resolving all solutions into {OUTPUT_PATH}..."
    draw(stdscr, state)

    with output_file:
        for solution in iter_solutions(grid):
            state.result_count += 1
            if state.first_solution is None:
                state.first_solution = solution

            output_file.write(solution + "\n")
            output_file.flush()

            state.status = f"Resolving... found {state.result_count} so far."
            draw(stdscr, state)

    if state.result_count == 0:
        state.status = f"Done. No solutions found. Wrote empty {OUTPUT_PATH}."
    else:
        state.status = f"Done. Wrote {state.result_count} to {OUTPUT_PATH}."


def handle_key(stdscr: curses.window, state: AppState, key: int) -> bool:
    if key in (ord("q"), ord("Q")):
        return False

    if key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT):
        move_cursor(state, key)
    elif key in (curses.KEY_DC, curses.KEY_BACKSPACE, 8, 127, ord("0"), ord("."), ord(" ")):
        clear_current_cell(state)
    elif ord("1") <= key <= ord("9"):
        set_current_cell(state, chr(key))
    elif key in (9,):
        state.focus = "button" if state.focus == "grid" else "grid"
    elif key in (curses.KEY_ENTER, 10, 13):
        resolve_current_grid(stdscr, state)

    return True


def run(stdscr: curses.window) -> None:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    stdscr.keypad(True)

    state = AppState(cells=[""] * BOARD_SIZE)
    running = True
    while running:
        draw(stdscr, state)
        running = handle_key(stdscr, state, stdscr.getch())


def main() -> int:
    curses.wrapper(run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
