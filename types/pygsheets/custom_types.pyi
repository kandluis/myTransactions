from _typeshed import Incomplete
from enum import Enum

class WorkSheetProperty(Enum):
    TITLE = "TITLE"
    ID = "ID"
    INDEX = "INDEX"

class ValueRenderOption(Enum):
    FORMATTED_VALUE = "FORMATTED_VALUE"
    UNFORMATTED_VALUE = "UNFORMATTED_VALUE"
    FORMULA = "FORMULA"

class DateTimeRenderOption(Enum):
    SERIAL_NUMBER = "SERIAL_NUMBER"
    FORMATTED_STRING = "FORMATTED_STRING"

class FormatType(Enum):
    CUSTOM: Incomplete
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    PERCENT = "PERCENT"
    CURRENCY = "CURRENCY"
    DATE = "DATE"
    TIME = "TIME"
    DATE_TIME = "DATE_TIME"
    SCIENTIFIC = "SCIENTIFIC"

class ExportType(Enum):
    XLS = "XLS"
    ODT = "ODT"
    PDF = "PDF"
    CSV = "CSV"
    TSV = "TSV"
    HTML = "HTML"

class HorizontalAlignment(Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    CENTER = "CENTER"
    NONE: Incomplete

class VerticalAlignment(Enum):
    TOP = "TOP"
    MIDDLE = "MIDDLE"
    BOTTOM = "BOTTOM"
    NONE: Incomplete

class ChartType(Enum):
    BAR = "BAR"
    LINE = "LINE"
    AREA = "AREA"
    COLUMN = "COLUMN"
    SCATTER = "SCATTER"
    COMBO = "COMBO"
    STEPPED_AREA = "STEPPED_AREA"
