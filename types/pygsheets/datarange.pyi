from _typeshed import Incomplete
from pygsheets.address import GridRange as GridRange
from pygsheets.exceptions import (
    CellNotFound as CellNotFound,
    InvalidArgumentValue as InvalidArgumentValue,
)

class DataRange:
    logger: Incomplete
    protected_properties: Incomplete
    grid_range: Incomplete
    def __init__(
        self,
        start: Incomplete | None = None,
        end: Incomplete | None = None,
        worksheet: Incomplete | None = None,
        name: str = "",
        data: Incomplete | None = None,
        name_id: Incomplete | None = None,
        namedjson: Incomplete | None = None,
        protectedjson: Incomplete | None = None,
        grange: Incomplete | None = None,
    ) -> None: ...
    @property
    def name(self): ...
    @name.setter
    def name(self, name) -> None: ...
    @property
    def name_id(self): ...
    @property
    def protect_id(self): ...
    @property
    def protected(self): ...
    @protected.setter
    def protected(self, value) -> None: ...
    @property
    def editors(self): ...
    @editors.setter
    def editors(self, value) -> None: ...
    @property
    def requesting_user_can_edit(self): ...
    @requesting_user_can_edit.setter
    def requesting_user_can_edit(self, value) -> None: ...
    @property
    def description(self): ...
    @description.setter
    def description(self, value) -> None: ...
    @property
    def start_addr(self): ...
    @start_addr.setter
    def start_addr(self, addr) -> None: ...
    @property
    def end_addr(self): ...
    @end_addr.setter
    def end_addr(self, addr) -> None: ...
    @property
    def range(self): ...
    @property
    def worksheet(self): ...
    @property
    def cells(self): ...
    def link(self, update: bool = True) -> None: ...
    def unlink(self) -> None: ...
    def fetch(self, only_data: bool = True) -> None: ...
    def apply_format(
        self,
        cell: Incomplete | None = None,
        fields: Incomplete | None = None,
        cell_json: Incomplete | None = None,
    ) -> None: ...
    def update_values(self, values: Incomplete | None = None) -> None: ...
    def sort(self, basecolumnindex: int = 0, sortorder: str = "ASCENDING") -> None: ...
    def clear(self, fields: str = "userEnteredValue") -> None: ...
    def update_named_range(self): ...
    def update_protected_range(self, fields: str = "*"): ...
    def update_borders(
        self,
        top: bool = False,
        right: bool = False,
        bottom: bool = False,
        left: bool = False,
        inner_horizontal: bool = False,
        inner_vertical: bool = False,
        style: str = "NONE",
        width: int = 1,
        red: int = 0,
        green: int = 0,
        blue: int = 0,
    ) -> None: ...
    def merge_cells(self, merge_type: str = "MERGE_ALL") -> None: ...
    def __getitem__(self, item): ...
    def __eq__(self, other): ...

class ProtectedRangeProperties:
    protected_id: Incomplete
    description: Incomplete
    warningOnly: Incomplete
    requestingUserCanEdit: Incomplete
    editors: Incomplete
    def __init__(self, api_obj: Incomplete | None = None) -> None: ...
    def set_json(self, api_obj) -> None: ...
    def to_json(self): ...
    def is_protected(self): ...
    def clear(self) -> None: ...