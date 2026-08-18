"""Make one safe request to check a saved Empower session."""

from __future__ import annotations

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import empower  # noqa: E402


EXIT_AVAILABLE = 0
EXIT_ERROR = 1
EXIT_CHALLENGED = 2
EXIT_SESSION_EXPIRED = 3


def check_saved_session(session_path: Path) -> int:
    """Check a saved session without attempting login or printing account data."""
    connection = empower.PersonalCapital()
    if not connection.load_session(str(session_path)):
        print(f"ERROR: Could not load saved session from {session_path}.")
        return EXIT_ERROR

    try:
        connection.get_account_data()
    except empower.PersonalCapitalCloudflareChallengeException as exc:
        print(f"CHALLENGED: {exc}")
        return EXIT_CHALLENGED
    except empower.PersonalCapitalSessionExpiredException:
        print("EXPIRED: The saved Empower session must be refreshed with MFA.")
        return EXIT_SESSION_EXPIRED
    except Exception as exc:
        print(f"ERROR: Session check failed: {exc}")
        return EXIT_ERROR

    print("AVAILABLE: The saved Empower session passed one account API check.")
    return EXIT_AVAILABLE


def main() -> int:
    session_path = Path(os.getenv("SESSION_FILE_PATH", ".session.pkl"))
    return check_saved_session(session_path)


if __name__ == "__main__":
    raise SystemExit(main())
