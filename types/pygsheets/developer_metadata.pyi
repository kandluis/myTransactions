from _typeshed import Incomplete

class DeveloperMetadataLookupDataFilter:
    spreadsheet_id: Incomplete
    sheet_id: Incomplete
    meta_filters: Incomplete
    def __init__(
        self,
        spreadsheet_id: Incomplete | None = None,
        sheet_id: Incomplete | None = None,
        meta_id: Incomplete | None = None,
        meta_key: Incomplete | None = None,
        meta_value: Incomplete | None = None,
    ) -> None: ...
    def to_json(self): ...
    @property
    def location(self): ...

class DeveloperMetadata:
    @classmethod
    def new(
        cls, key, value, client, spreadsheet_id, sheet_id: Incomplete | None = None
    ): ...
    key: Incomplete
    value: Incomplete
    client: Incomplete
    spreadsheet_id: Incomplete
    sheet_id: Incomplete
    def __init__(
        self,
        meta_id,
        key,
        value,
        client,
        spreadsheet_id,
        sheet_id: Incomplete | None = None,
    ) -> None: ...
    @property
    def id(self): ...
    def fetch(self) -> None: ...
    def update(self) -> None: ...
    def delete(self) -> None: ...
