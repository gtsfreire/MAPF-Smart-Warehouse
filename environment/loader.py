"""
Loader para mapas no formato MovingAI.

Cabeçalho esperado:
  type octile
  height H
  width  W
  map
  ...HxW linhas com W chars...

Caracteres tratados como obstáculo: '@', 'O', 'T', '#'
Tudo o resto é considerado livre ('.', 'G', 'S', etc.).
"""
#gtsfreire
from __future__ import annotations

from pathlib import Path

from environment.grid import Cell, Grid


OBSTACLE_CHARS = {"@", "O", "T", "#"}


def load_map(path: Path) -> Grid:
    """
    Carrega um mapa MovingAI e devolve uma Grid preenchida.

    Raises:
        FileNotFoundError: se o ficheiro não existe.
        ValueError: se o cabeçalho ou o corpo forem inválidos.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Mapa não encontrado: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4:
        raise ValueError(f"Mapa demasiado curto: {path}")

    # Procura as linhas de cabeçalho de forma tolerante a ordem.
    header: dict[str, str] = {}
    map_start = None
    for i, line in enumerate(lines[:10]):
        stripped = line.strip().lower()
        if stripped.startswith("height"):
            header["height"] = stripped.split()[1]
        elif stripped.startswith("width"):
            header["width"] = stripped.split()[1]
        elif stripped == "map":
            map_start = i + 1
            break

    if map_start is None or "height" not in header or "width" not in header:
        raise ValueError(f"Cabeçalho MovingAI inválido em: {path}")

    try:
        height = int(header["height"])
        width = int(header["width"])
    except ValueError as exc:
        raise ValueError(f"Dimensões inválidas no mapa: {path}") from exc

    body = lines[map_start : map_start + height]
    if len(body) < height:
        raise ValueError(
            f"Mapa truncado: esperado {height} linhas, obtido {len(body)} ({path})"
        )

    grid = Grid(width, height)
    for row, line in enumerate(body):
        # tolera linhas mais curtas/longas que width
        for col in range(min(width, len(line))):
            ch = line[col]
            if ch in OBSTACLE_CHARS:
                grid.cells[row][col] = Cell.OBSTACLE

    return grid
