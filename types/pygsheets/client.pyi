from _typeshed import Incomplete
from pygsheets.custom_types import (
    DateTimeRenderOption as DateTimeRenderOption,
    ValueRenderOption as ValueRenderOption,
)
from pygsheets.drive import DriveAPIWrapper as DriveAPIWrapper
from pygsheets.exceptions import (
    NoValidUrlKeyFound as NoValidUrlKeyFound,
    SpreadsheetNotFound as SpreadsheetNotFound,
)
from pygsheets.sheet import SheetAPIWrapper as SheetAPIWrapper
from pygsheets.spreadsheet import Spreadsheet
from typing import Type

GOOGLE_SHEET_CELL_UPDATES_LIMIT: int

class Client:
    spreadsheet_cls: Type[Spreadsheet] = Spreadsheet
    oauth: Incomplete
    logger: Incomplete
    sheet: Incomplete
    drive: Incomplete
    def __init__(
        self,
        credentials,
        retries: int = 3,
        http: Incomplete | None = None,
        check: bool = True,
        seconds_per_quota: int = 100,
    ) -> None: ...
    @property
    def teamDriveId(self) -> str: ...
    @teamDriveId.setter
    def teamDriveId(self, value: str) -> None: ...
    def spreadsheet_ids(self, query: Incomplete | None = None) -> list[str]: ...
    def set_batch_mode(self, value) -> None: ...
    def run_batch(self) -> None: ...
    def spreadsheet_titles(self, query: Incomplete | None = None) -> list[str]: ...
    def create(
        self,
        title: str,
        template: str | Spreadsheet | None = None,
        folder: str | None = None,
        folder_name: str | None = None,
        **kwargs
    ) -> Spreadsheet: ...
    def open(self, title: str) -> Spreadsheet: ...
    def open_by_key(self, key: str) -> Spreadsheet: ...
    def open_by_url(self, url: str) -> Spreadsheet: ...
    def open_all(self, query: str = "") -> list[Spreadsheet]: ...
    def open_as_json(self, key: str): ...
    def get_range(
        self,
        spreadsheet_id: str,
        value_range: str | None = None,
        major_dimension: str = "ROWS",
        value_render_option=...,
        date_time_render_option=...,
        value_ranges: Incomplete | None = None,
    ) -> list[list[str]]: ...
