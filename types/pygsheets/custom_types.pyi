from _typeshed import Incomplete
from enum import Enum

class WorkSheetProperty(Enum):
    TITLE: str
    ID: str
    INDEX: str

class ValueRenderOption(Enum):
    FORMATTED_VALUE: str
    UNFORMATTED_VALUE: str
    FORMULA: str

class DateTimeRenderOption(Enum):
    SERIAL_NUMBER: str
    FORMATTED_STRING: str

class FormatType(Enum):
    CUSTOM: Incomplete
    TEXT: str
    NUMBER: str
    PERCENT: str
    CURRENCY: str
    DATE: str
    TIME: str
    DATE_TIME: str
    SCIENTIFIC: str

class ExportType(Enum):
    XLS: str
    ODT: str
    PDF: str
    CSV: str
    TSV: str
    HTML: str

class HorizontalAlignment(Enum):
    LEFT: str
    RIGHT: str
    CENTER: str
    NONE: Incomplete

class VerticalAlignment(Enum):
    TOP: str
    MIDDLE: str
    BOTTOM: str
    NONE: Incomplete

class ChartType(Enum):
    BAR: str
    LINE: str
    AREA: str
    COLUMN: str
    SCATTER: str
    COMBO: str
    STEPPED_AREA: str
