class PyGsheetsException(Exception): ...
class AuthenticationError(PyGsheetsException): ...
class SpreadsheetNotFound(PyGsheetsException): ...
class WorksheetNotFound(PyGsheetsException): ...
class CellNotFound(PyGsheetsException): ...
class RangeNotFound(PyGsheetsException): ...
class TeamDriveNotFound(PyGsheetsException): ...
class FolderNotFound(PyGsheetsException): ...
class NoValidUrlKeyFound(PyGsheetsException): ...
class IncorrectCellLabel(PyGsheetsException): ...
class RequestError(PyGsheetsException): ...
class InvalidArgumentValue(PyGsheetsException): ...
class InvalidUser(PyGsheetsException): ...
class CannotRemoveOwnerError(PyGsheetsException): ...
