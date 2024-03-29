from pygsheets.custom_types import *
from _typeshed import Incomplete
from pygsheets.address import Address as Address, GridRange as GridRange
from pygsheets.exceptions import (
    CellNotFound as CellNotFound,
    IncorrectCellLabel as IncorrectCellLabel,
    InvalidArgumentValue as InvalidArgumentValue,
)
from pygsheets.utils import (
    format_addr as format_addr,
    format_color as format_color,
    is_number as is_number,
)

class Cell:
    format: Incomplete
    text_format: Incomplete
    text_rotation: Incomplete
    borders: Incomplete
    parse_value: bool
    is_dirty: bool
    def __init__(
        self,
        pos,
        val: str = "",
        worksheet: Incomplete | None = None,
        cell_data: Incomplete | None = None,
    ) -> None: ...
    @property
    def row(self): ...
    @row.setter
    def row(self, row) -> None: ...
    @property
    def col(self): ...
    @col.setter
    def col(self, col) -> None: ...
    @property
    def label(self): ...
    @label.setter
    def label(self, label) -> None: ...
    @property
    def address(self): ...
    @address.setter
    def address(self, value) -> None: ...
    @property
    def value(self): ...
    @value.setter
    def value(self, value) -> None: ...
    @property
    def value_unformatted(self): ...
    @property
    def formula(self): ...
    @formula.setter
    def formula(self, formula) -> None: ...
    @property
    def horizontal_alignment(self): ...
    @horizontal_alignment.setter
    def horizontal_alignment(self, value) -> None: ...
    @property
    def vertical_alignment(self): ...
    @vertical_alignment.setter
    def vertical_alignment(self, value) -> None: ...
    @property
    def wrap_strategy(self): ...
    @wrap_strategy.setter
    def wrap_strategy(self, wrap_strategy) -> None: ...
    @property
    def note(self): ...
    @note.setter
    def note(self, note) -> None: ...
    @property
    def color(self): ...
    @color.setter
    def color(self, value) -> None: ...
    @property
    def simple(self): ...
    @simple.setter
    def simple(self, value) -> None: ...
    def set_text_format(self, attribute, value): ...
    def set_number_format(self, format_type, pattern: str = ""): ...
    def set_text_rotation(self, attribute, value): ...
    def set_horizontal_alignment(self, value): ...
    def set_vertical_alignment(self, value): ...
    def set_value(self, value): ...
    def unlink(self): ...
    def link(self, worksheet: Incomplete | None = None, update: bool = False): ...
    def neighbour(self, position): ...
    def fetch(self, keep_simple: bool = False): ...
    def refresh(self) -> None: ...
    def update(
        self,
        force: bool = False,
        get_request: bool = False,
        worksheet_id: Incomplete | None = None,
    ): ...
    def get_json(self): ...
    hyperlink: Incomplete
    def set_json(self, cell_data) -> None: ...
    def __setattr__(self, key, value) -> None: ...
    def __eq__(self, other): ...
