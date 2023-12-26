from _typeshed import Incomplete
from pygsheets.custom_types import (
    DateTimeRenderOption as DateTimeRenderOption,
    ValueRenderOption as ValueRenderOption,
)
from pygsheets.exceptions import InvalidArgumentValue as InvalidArgumentValue
from pygsheets.spreadsheet import Spreadsheet as Spreadsheet
from pygsheets.utils import format_addr as format_addr

GOOGLE_SHEET_CELL_UPDATES_LIMIT: int
DISCOVERY_SERVICE_URL: str

class SheetAPIWrapper:
    logger: Incomplete
    service: Incomplete
    retries: Incomplete
    seconds_per_quota: Incomplete
    check: Incomplete
    batch_mode: bool
    batched_requests: Incomplete
    def __init__(
        self,
        http,
        data_path,
        seconds_per_quota: int = 100,
        retries: int = 1,
        logger=...,
        check: bool = True,
    ) -> None: ...
    def set_batch_mode(self, mode) -> None: ...
    def run_batch(self): ...
    def batch_update(self, spreadsheet_id, requests, **kwargs): ...
    def create(self, title, template: Incomplete | None = None, **kwargs): ...
    def get(self, spreadsheet_id, **kwargs): ...
    def update_sheet_properties_request(self, spreadsheet_id, properties, fields): ...
    def developer_metadata_get(self, spreadsheet_id, metadata_id): ...
    def developer_metadata_search(self, spreadsheet_id, data_filter): ...
    def sheets_copy_to(
        self, source_spreadsheet_id, worksheet_id, destination_spreadsheet_id, **kwargs
    ): ...
    def values_append(
        self, spreadsheet_id, values, major_dimension, range, **kwargs
    ): ...
    def values_batch_clear(self, spreadsheet_id, ranges) -> None: ...
    def values_batch_get(
        self,
        spreadsheet_id,
        value_ranges,
        major_dimension: str = "ROWS",
        value_render_option=...,
        date_time_render_option=...,
    ): ...
    def values_batch_update(self, spreadsheet_id, body, parse: bool = True) -> None: ...
    def values_batch_update_by_data_filter(
        self, spreadsheet_id, data, parse: bool = True
    ) -> None: ...
    def values_get(
        self,
        spreadsheet_id,
        value_range,
        major_dimension: str = "ROWS",
        value_render_option=...,
        date_time_render_option=...,
    ): ...
    def developer_metadata_delete(self, spreadsheet_id, data_filter) -> None: ...
    def developer_metadata_create(self, spreadsheet_id, key, value, location): ...
    def developer_metadata_update(
        self, spreadsheet_id, key, value, location, data_filter
    ) -> None: ...
