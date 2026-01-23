import os
import tempfile
import pytest
from unittest.mock import MagicMock
from empower import PersonalCapital


class TestPersonalCapitalSession:
    def test_save_and_load_session(self):
        # Create a temporary file for the session
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            session_file = tmp.name

        try:
            # Initialize PersonalCapital and set some dummy data
            pc_save = PersonalCapital()
            pc_save._csrf = "test_csrf_token"
            pc_save._email = "test@example.com"
            pc_save.session.cookies.set("session_id", "12345")

            # Save the session
            pc_save.save_session(session_file)

            # Verify file exists
            assert os.path.exists(session_file)

            # Initialize a new PersonalCapital instance
            pc_load = PersonalCapital()

            # Load the session
            result = pc_load.load_session(session_file)

            # Assert loading was successful
            assert result is True
            assert pc_load._csrf == "test_csrf_token"
            assert pc_load._email == "test@example.com"
            assert pc_load.session.cookies.get("session_id") == "12345"

        finally:
            # Clean up
            if os.path.exists(session_file):
                os.remove(session_file)

    def test_load_nonexistent_session(self):
        pc = PersonalCapital()
        result = pc.load_session("nonexistent_file.pkl")
        assert result is False

    def test_load_corrupted_session(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"not a pickle file")
            session_file = tmp.name

        try:
            pc = PersonalCapital()
            # Should catch the exception and return False
            result = pc.load_session(session_file)
            assert result is False
        finally:
            if os.path.exists(session_file):
                os.remove(session_file)
