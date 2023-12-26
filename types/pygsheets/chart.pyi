from _typeshed import Incomplete
from pygsheets.cell import Cell as Cell
from pygsheets.custom_types import ChartType as ChartType
from pygsheets.exceptions import InvalidArgumentValue as InvalidArgumentValue
from pygsheets.utils import format_addr as format_addr

class Chart:
    def __init__(
        self,
        worksheet,
        domain: Incomplete | None = None,
        ranges: Incomplete | None = None,
        chart_type: Incomplete | None = None,
        title: str = "",
        anchor_cell: Incomplete | None = None,
        json_obj: Incomplete | None = None,
    ) -> None: ...
    @property
    def title(self): ...
    @title.setter
    def title(self, new_title) -> None: ...
    @property
    def domain(self): ...
    @domain.setter
    def domain(self, new_domain) -> None: ...
    @property
    def chart_type(self): ...
    @chart_type.setter
    def chart_type(self, new_chart_type) -> None: ...
    @property
    def ranges(self): ...
    @ranges.setter
    def ranges(self, new_ranges) -> None: ...
    @property
    def title_font_family(self): ...
    @title_font_family.setter
    def title_font_family(self, new_title_font_family) -> None: ...
    @property
    def font_name(self): ...
    @font_name.setter
    def font_name(self, new_font_name) -> None: ...
    @property
    def legend_position(self): ...
    @legend_position.setter
    def legend_position(self, new_legend_position) -> None: ...
    @property
    def id(self): ...
    @property
    def anchor_cell(self): ...
    @anchor_cell.setter
    def anchor_cell(self, new_anchor_cell) -> None: ...
    def delete(self) -> None: ...
    def refresh(self) -> None: ...
    def update_chart(self) -> None: ...
    def get_json(self): ...
    def set_json(self, chart_data) -> None: ...
