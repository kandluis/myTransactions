from _typeshed import Incomplete
from pygsheets.exceptions import (
    IncorrectCellLabel as IncorrectCellLabel,
    InvalidArgumentValue as InvalidArgumentValue,
)

class Address:
    allow_non_single: Incomplete
    def __init__(self, value, allow_non_single: bool = False) -> None: ...
    @property
    def label(self): ...
    @property
    def index(self): ...
    def __iter__(self): ...
    def __getitem__(self, item): ...
    def __setitem__(self, key, value) -> None: ...
    def __add__(self, other): ...
    def __sub__(self, other): ...
    def __eq__(self, other): ...
    def __ne__(self, other): ...
    def __bool__(self) -> bool: ...
    __nonzero__ = __bool__

class GridRange:
    def __init__(
        self,
        label: Incomplete | None = None,
        worksheet: Incomplete | None = None,
        start: Incomplete | None = None,
        end: Incomplete | None = None,
        worksheet_title: Incomplete | None = None,
        worksheet_id: Incomplete | None = None,
        propertiesjson: Incomplete | None = None,
    ) -> None: ...
    @property
    def start(self): ...
    @start.setter
    def start(self, value) -> None: ...
    @property
    def end(self): ...
    @end.setter
    def end(self, value) -> None: ...
    @property
    def indexes(self): ...
    @indexes.setter
    def indexes(self, value) -> None: ...
    @property
    def label(self): ...
    @label.setter
    def label(self, value) -> None: ...
    @property
    def worksheet_id(self): ...
    @worksheet_id.setter
    def worksheet_id(self, value) -> None: ...
    @property
    def worksheet_title(self): ...
    @worksheet_title.setter
    def worksheet_title(self, value) -> None: ...
    @staticmethod
    def create(data, wks: Incomplete | None = None): ...
    def set_worksheet(self, value) -> None: ...
    def to_json(self): ...
    def set_json(self, namedjson) -> None: ...
    def get_bounded_indexes(self): ...
    @property
    def height(self): ...
    @property
    def width(self): ...
    def contains(self, address): ...
    def __eq__(self, other): ...
    def __ne__(self, other): ...
    def __contains__(self, item) -> bool: ...
    def __iter__(self): ...