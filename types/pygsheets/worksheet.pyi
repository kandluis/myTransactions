from pygsheets.custom_types import *
from _typeshed import Incomplete
from pygsheets.address import Address as Address, GridRange as GridRange
from pygsheets.cell import Cell as Cell
from pygsheets.chart import Chart as Chart
from pygsheets.datarange import DataRange as DataRange
from pygsheets.developer_metadata import (
    DeveloperMetadata as DeveloperMetadata,
    DeveloperMetadataLookupDataFilter as DeveloperMetadataLookupDataFilter,
)
from pygsheets.exceptions import (
    CellNotFound as CellNotFound,
    InvalidArgumentValue as InvalidArgumentValue,
    RangeNotFound as RangeNotFound,
)
from pygsheets.utils import (
    allow_gridrange as allow_gridrange,
    batchable as batchable,
    format_addr as format_addr,
    fullmatch as fullmatch,
    get_boolean_condition as get_boolean_condition,
    get_color_style as get_color_style,
    numericise_all as numericise_all,
)
import pandas as pd

class Worksheet:
    logger: Incomplete
    spreadsheet: Incomplete
    client: Incomplete
    jsonSheet: Incomplete
    data_grid: Incomplete
    grid_update_time: Incomplete
    def __init__(self, spreadsheet, jsonSheet) -> None: ...
    @property
    def id(self): ...
    @property
    def index(self): ...
    @index.setter
    def index(self, index) -> None: ...
    @property
    def title(self): ...
    @title.setter
    def title(self, title) -> None: ...
    @property
    def hidden(self): ...
    @hidden.setter
    def hidden(self, hidden) -> None: ...
    @property
    def url(self): ...
    @property
    def rows(self): ...
    @rows.setter
    def rows(self, row_count) -> None: ...
    @property
    def cols(self): ...
    @cols.setter
    def cols(self, col_count) -> None: ...
    @property
    def frozen_rows(self): ...
    @frozen_rows.setter
    def frozen_rows(self, row_count) -> None: ...
    @property
    def frozen_cols(self): ...
    @frozen_cols.setter
    def frozen_cols(self, col_count) -> None: ...
    @property
    def merged_ranges(self): ...
    @property
    def linked(self): ...
    def refresh(self, update_grid: bool = False) -> None: ...
    def link(self, syncToCloud: bool = True) -> None: ...
    def unlink(self, save_grid: bool = True) -> None: ...
    def sync(self) -> None: ...
    def cell(self, addr): ...
    def range(self, crange, returnas: str = "cells"): ...
    def get_value(self, addr, value_render=...): ...
    def get_values(
        self,
        start,
        end,
        returnas: str = "matrix",
        majdim: str = "ROWS",
        include_tailing_empty: bool = True,
        include_tailing_empty_rows: bool = False,
        value_render=...,
        date_time_render_option=...,
        grange: Incomplete | None = None,
        **kwargs
    ): ...
    def get_values_batch(
        self,
        ranges,
        majdim: str = "ROWS",
        value_render=...,
        date_time_render_option=...,
        **kwargs
    ): ...
    def get_all_values(
        self,
        returnas: str = "matrix",
        majdim: str = "ROWS",
        include_tailing_empty: bool = True,
        include_tailing_empty_rows: bool = True,
        **kwargs
    ): ...
    def get_all_records(
        self,
        empty_value: str = "",
        head: int = 1,
        majdim: str = "ROWS",
        numericise_data: bool = True,
        **kwargs
    ): ...
    def get_row(
        self,
        row,
        returnas: str = "matrix",
        include_tailing_empty: bool = True,
        **kwargs
    ): ...
    def get_col(
        self,
        col,
        returnas: str = "matrix",
        include_tailing_empty: bool = True,
        **kwargs
    ): ...
    def get_gridrange(self, start, end): ...
    def update_cell(self, **kwargs) -> None: ...
    def update_value(self, addr, val, parse: Incomplete | None = None): ...
    def update_values(
        self,
        crange: Incomplete | None = None,
        values: Incomplete | None = None,
        cell_list: Incomplete | None = None,
        extend: bool = False,
        majordim: str = "ROWS",
        parse: Incomplete | None = None,
    ): ...
    def update_values_batch(
        self, ranges, values, majordim: str = "ROWS", parse: Incomplete | None = None
    ) -> None: ...
    def update_cells_prop(self, **kwargs) -> None: ...
    def update_cells(self, cell_list, fields: str = "*"): ...
    def update_col(self, index, values, row_offset: int = 0): ...
    def update_row(self, index, values, col_offset: int = 0): ...
    def resize(
        self, rows: Incomplete | None = None, cols: Incomplete | None = None
    ) -> None: ...
    def add_rows(self, rows) -> None: ...
    def add_cols(self, cols) -> None: ...
    def delete_cols(self, index, number: int = 1): ...
    def delete_rows(self, index, number: int = 1): ...
    def insert_cols(
        self,
        col,
        number: int = 1,
        values: Incomplete | None = None,
        inherit: bool = False,
    ): ...
    def insert_rows(
        self,
        row,
        number: int = 1,
        values: Incomplete | None = None,
        inherit: bool = False,
    ): ...
    def clear(
        self,
        start: str = "A1",
        end: Incomplete | None = None,
        fields: str = "userEnteredValue",
    ): ...
    def adjust_column_width(
        self, start, end: Incomplete | None = None, pixel_size: Incomplete | None = None
    ): ...
    def apply_format(
        self, ranges, format_info, fields: str = "userEnteredFormat"
    ) -> None: ...
    def update_dimensions_visibility(
        self,
        start,
        end: Incomplete | None = None,
        dimension: str = "ROWS",
        hidden: bool = True,
    ): ...
    def hide_dimensions(
        self, start, end: Incomplete | None = None, dimension: str = "ROWS"
    ) -> None: ...
    def show_dimensions(
        self, start, end: Incomplete | None = None, dimension: str = "ROWS"
    ) -> None: ...
    def adjust_row_height(
        self, start, end: Incomplete | None = None, pixel_size: Incomplete | None = None
    ): ...
    def append_table(
        self,
        values,
        start: str = "A1",
        end: Incomplete | None = None,
        dimension: str = "ROWS",
        overwrite: bool = False,
        **kwargs
    ): ...
    def replace(
        self, pattern, replacement: Incomplete | None = None, **kwargs
    ) -> None: ...
    def find(
        self,
        pattern,
        searchByRegex: bool = False,
        matchCase: bool = False,
        matchEntireCell: bool = False,
        includeFormulas: bool = False,
        cols: Incomplete | None = None,
        rows: Incomplete | None = None,
        forceFetch: bool = True,
    ): ...
    def create_named_range(
        self,
        name,
        start: Incomplete | None = None,
        end: Incomplete | None = None,
        grange: Incomplete | None = None,
        returnas: str = "range",
    ): ...
    def get_named_range(self, name): ...
    def get_named_ranges(self, name: str = ""): ...
    def delete_named_range(self, name, range_id: str = ""): ...
    def create_protected_range(
        self,
        start: Incomplete | None = None,
        end: Incomplete | None = None,
        grange: Incomplete | None = None,
        named_range_id: Incomplete | None = None,
        returnas: str = "range",
    ): ...
    def remove_protected_range(self, range_id): ...
    def get_protected_ranges(self): ...
    def set_dataframe(
        self,
        df,
        start,
        copy_index: bool = False,
        copy_head: bool = True,
        extend: bool = False,
        fit: bool = False,
        escape_formulae: bool = False,
        **kwargs
    ): ...
    def get_as_df(
        self,
        has_header: bool = True,
        index_column: int | None = None,
        start: str | None = None,
        end: str | None = None,
        numerize: bool = True,
        empty_value: str = "",
        value_render=...,
        **kwargs
    ) -> pd.DataFrame: ...
    def export(
        self, file_format=..., filename: Incomplete | None = None, path: str = ""
    ) -> None: ...
    def copy_to(self, spreadsheet_id): ...
    def sort_range(
        self, start, end, basecolumnindex: int = 0, sortorder: str = "ASCENDING"
    ): ...
    def add_chart(
        self,
        domain,
        ranges,
        title: Incomplete | None = None,
        chart_type=...,
        anchor_cell: Incomplete | None = None,
    ): ...
    def get_charts(self, title: Incomplete | None = None): ...
    def set_data_validation(
        self,
        start: Incomplete | None = None,
        end: Incomplete | None = None,
        condition_type: Incomplete | None = None,
        condition_values: Incomplete | None = None,
        grange: Incomplete | None = None,
        **kwargs
    ) -> None: ...
    def set_basic_filter(
        self,
        start: Incomplete | None = None,
        end: Incomplete | None = None,
        grange: Incomplete | None = None,
        sort_order: Incomplete | None = None,
        sort_foreground_color: Incomplete | None = None,
        sort_background_color: Incomplete | None = None,
        sort_column_index: Incomplete | None = None,
        filter_column_index: Incomplete | None = None,
        hidden_values: Incomplete | None = None,
        condition_type: Incomplete | None = None,
        condition_values: Incomplete | None = None,
        filter_foreground_color: Incomplete | None = None,
        filter_background_color: Incomplete | None = None,
    ) -> None: ...
    def clear_basic_filter(self) -> None: ...
    def add_conditional_formatting(
        self,
        start,
        end,
        condition_type,
        format,
        condition_values: Incomplete | None = None,
        grange: Incomplete | None = None,
    ) -> None: ...
    def merge_cells(
        self,
        start: Incomplete | None = None,
        end: Incomplete | None = None,
        merge_type: str = "MERGE_ALL",
        grange: Incomplete | None = None,
    ) -> None: ...
    def get_developer_metadata(self, key: Incomplete | None = None): ...
    def create_developer_metadata(self, key, value: Incomplete | None = None): ...
    def __eq__(self, other): ...
    def __iter__(self): ...
    def __getitem__(self, item): ...
