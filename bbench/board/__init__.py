"""Breadboard model, automatic layout and the checker."""
from .model import ROWS, COLS, RAILS, legs  # noqa: F401
from .checker import check_boards, connectivity  # noqa: F401
from .autolayout import layout  # noqa: F401
