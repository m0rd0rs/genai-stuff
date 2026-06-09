#!/usr/bin/env python3
"""Exhaustive recursive Sudoku solver.

Usage:
    python3 sudoku_solver.py "530070000600195000098000060800060003400803001700020006060000280000419005000080079"

The puzzle must contain 81 cells. Digits 1-9 are givens, and 0 or . are empty
cells. Every solution is printed and written as one 81-digit string per line.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


ALL_DIGITS_MASK = 0b1111111110
BOARD_SIZE = 81
GRID_WIDTH = 9


def normalize_grid(text: str) -> str:
    """Return an 81-character digit string, converting dots to zeroes."""
    cells: list[str] = []
    bad_chars: list[str] = []

    for char in text:
        if char in "0123456789":
            cells.append(char)
        elif char == ".":
            cells.append("0")
        elif char.isspace():
            continue
        else:
            bad_chars.append(char)

    if bad_chars:
        unique_bad_chars = "".join(sorted(set(bad_chars)))
        raise ValueError(f"grid contains unsupported character(s): {unique_bad_chars!r}")

    if len(cells) != BOARD_SIZE:
        raise ValueError(f"grid must contain exactly 81 cells, got {len(cells)}")

    return "".join(cells)


def format_grid(grid: str) -> str:
    """Format an 81-character grid string as a readable 9x9 Sudoku board."""
    lines: list[str] = []
    border = "+-------+-------+-------+"

    for row_index in range(GRID_WIDTH):
        if row_index % 3 == 0:
            lines.append(border)

        row = grid[row_index * GRID_WIDTH : (row_index + 1) * GRID_WIDTH]
        groups = []
        for group_start in range(0, GRID_WIDTH, 3):
            group = row[group_start : group_start + 3]
            groups.append(" ".join(cell if cell != "0" else "." for cell in group))
        lines.append("| " + " | ".join(groups) + " |")

    lines.append(border)
    return "\n".join(lines)


def validate_givens(grid: str) -> None:
    """Reject puzzles that contain duplicate fixed values in any unit."""
    units: list[list[int]] = []

    for row in range(GRID_WIDTH):
        units.append([row * GRID_WIDTH + col for col in range(GRID_WIDTH)])

    for col in range(GRID_WIDTH):
        units.append([row * GRID_WIDTH + col for row in range(GRID_WIDTH)])

    for box_row in range(0, GRID_WIDTH, 3):
        for box_col in range(0, GRID_WIDTH, 3):
            units.append(
                [
                    (box_row + row) * GRID_WIDTH + box_col + col
                    for row in range(3)
                    for col in range(3)
                ]
            )

    for unit in units:
        seen: dict[str, int] = {}
        for index in unit:
            value = grid[index]
            if value == "0":
                continue
            if value in seen:
                first_row, first_col = divmod(seen[value], GRID_WIDTH)
                row, col = divmod(index, GRID_WIDTH)
                raise ValueError(
                    f"duplicate {value} at row {first_row + 1}, column {first_col + 1} "
                    f"and row {row + 1}, column {col + 1}"
                )
            seen[value] = index


def bit_to_digit(mask: int) -> str:
    return str(mask.bit_length() - 1)


def count_bits(mask: int) -> int:
    return bin(mask).count("1")


def iter_digit_masks(mask: int) -> Iterable[int]:
    while mask:
        digit_mask = mask & -mask
        yield digit_mask
        mask ^= digit_mask


def iter_solutions(grid: str, max_solutions: int | None = None) -> Iterable[str]:
    """Yield each solution found by recursive backtracking."""
    board = list(grid)
    row_masks = [0] * GRID_WIDTH
    col_masks = [0] * GRID_WIDTH
    box_masks = [0] * GRID_WIDTH
    empty_cells: set[int] = set()
    solutions_found = 0

    for index, value in enumerate(board):
        row, col = divmod(index, GRID_WIDTH)
        box = (row // 3) * 3 + (col // 3)
        if value == "0":
            empty_cells.add(index)
            continue

        mask = 1 << int(value)
        row_masks[row] |= mask
        col_masks[col] |= mask
        box_masks[box] |= mask

    def candidate_mask(index: int) -> int:
        row, col = divmod(index, GRID_WIDTH)
        box = (row // 3) * 3 + (col // 3)
        used = row_masks[row] | col_masks[col] | box_masks[box]
        return ALL_DIGITS_MASK & ~used

    def choose_cell() -> tuple[int | None, int]:
        best_index: int | None = None
        best_mask = 0
        best_count = 10

        for index in empty_cells:
            mask = candidate_mask(index)
            count = count_bits(mask)
            if count == 0:
                return index, 0
            if count < best_count:
                best_index = index
                best_mask = mask
                best_count = count
                if count == 1:
                    break

        return best_index, best_mask

    def search() -> Iterable[str]:
        nonlocal solutions_found

        if max_solutions is not None and solutions_found >= max_solutions:
            return

        if not empty_cells:
            solutions_found += 1
            yield "".join(board)
            return

        index, mask = choose_cell()
        if index is None or mask == 0:
            return

        row, col = divmod(index, GRID_WIDTH)
        box = (row // 3) * 3 + (col // 3)
        empty_cells.remove(index)

        for digit_mask in iter_digit_masks(mask):
            board[index] = bit_to_digit(digit_mask)
            row_masks[row] |= digit_mask
            col_masks[col] |= digit_mask
            box_masks[box] |= digit_mask

            yield from search()

            row_masks[row] ^= digit_mask
            col_masks[col] ^= digit_mask
            box_masks[box] ^= digit_mask
            board[index] = "0"

            if max_solutions is not None and solutions_found >= max_solutions:
                break

        empty_cells.add(index)

    yield from search()


def solve_all(grid: str, max_solutions: int | None = None) -> list[str]:
    """Return every solution found by recursive backtracking."""
    return list(iter_solutions(grid, max_solutions))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Solve a 9x9 Sudoku puzzle recursively and write all solutions."
    )
    parser.add_argument(
        "grid",
        help="81 cells as a quoted string. Digits 1-9 are givens; 0 or . are empty.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="sudoku_solutions.txt",
        help="file to write solution strings to, one 81-digit string per line",
    )
    parser.add_argument(
        "--max-solutions",
        type=int,
        default=None,
        help="optional safety cap for very open puzzles; omitted means exhaustive",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.max_solutions is not None and args.max_solutions < 1:
        print("--max-solutions must be greater than zero", file=sys.stderr)
        return 2

    try:
        grid = normalize_grid(args.grid)
        validate_givens(grid)
    except ValueError as exc:
        print(f"Invalid puzzle: {exc}", file=sys.stderr)
        return 2

    print("Input grid:")
    print(format_grid(grid))
    print()

    output_path = Path(args.output)
    solution_count = 0

    with output_path.open("w", encoding="utf-8") as output_file:
        for solution_count, solution in enumerate(
            iter_solutions(grid, args.max_solutions), start=1
        ):
            output_file.write(solution + "\n")
            output_file.flush()

            print(f"Solution {solution_count}:")
            print(format_grid(solution))
            print(solution)
            print(flush=True)

    if solution_count == 0:
        print("No solutions found.")
        print(f"Wrote empty result file: {output_path}")
        return 1

    limit_note = ""
    if args.max_solutions is not None and solution_count >= args.max_solutions:
        limit_note = f" Reached --max-solutions={args.max_solutions}."

    plural = "solution" if solution_count == 1 else "solutions"
    print(f"Found {solution_count} {plural}.{limit_note}")
    print(f"Wrote solution strings to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
