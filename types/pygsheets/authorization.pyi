from _typeshed import Incomplete
from pygsheets.client import Client

def authorize(
    client_secret: str = "client_secret.json",
    service_account_file: str | None = None,
    service_account_env_var: str | None = None,
    service_account_json: str | None = None,
    credentials_directory: str = "",
    scopes: tuple[str, ...] = (
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ),
    custom_credentials: Incomplete | None = None,
    local: bool = False,
    **kwargs
) -> Client: ...
