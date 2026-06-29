import pytest
from shared.errors import (
    AmbiguousProjectNameError,
    AuthRequiredError,
    DocumentNotFoundError,
    FileAlreadyExistsError,
    FolderAlreadyExistsError,
    GoogleApiError,
    InkClerkError,
    NoDraftError,
    PermissionDeniedError,
    ProjectNotFoundError,
)


class TestToDict:
    def test_base_error_to_dict_structure(self):
        err = InkClerkError("something went wrong")
        result = err.to_dict()
        assert result == {"error": "INTERNAL_ERROR", "message": "something went wrong"}

    def test_to_dict_uses_subclass_code(self):
        err = ProjectNotFoundError("my project")
        result = err.to_dict()
        assert result["error"] == "PROJECT_NOT_FOUND"
        assert result["message"] == "my project"

    def test_to_dict_keys_are_exactly_error_and_message(self):
        err = InkClerkError("x")
        assert set(err.to_dict().keys()) == {"error", "message"}


class TestErrorCodes:
    def test_base_code(self):
        assert InkClerkError.code == "INTERNAL_ERROR"

    def test_project_not_found(self):
        assert ProjectNotFoundError.code == "PROJECT_NOT_FOUND"

    def test_ambiguous_project_name(self):
        assert AmbiguousProjectNameError.code == "AMBIGUOUS_PROJECT_NAME"

    def test_document_not_found(self):
        assert DocumentNotFoundError.code == "FILE_NOT_FOUND"

    def test_file_already_exists(self):
        assert FileAlreadyExistsError.code == "FILE_ALREADY_EXISTS"

    def test_folder_already_exists(self):
        assert FolderAlreadyExistsError.code == "FOLDER_ALREADY_EXISTS"

    def test_no_draft(self):
        assert NoDraftError.code == "NO_DRAFT"

    def test_auth_required(self):
        assert AuthRequiredError.code == "AUTH_REQUIRED"

    def test_google_api_error(self):
        assert GoogleApiError.code == "GOOGLE_API_ERROR"

    def test_permission_denied(self):
        assert PermissionDeniedError.code == "PERMISSION_DENIED"


class TestInheritance:
    def test_all_subclasses_are_inkclerk_errors(self):
        subclasses = [
            ProjectNotFoundError,
            AmbiguousProjectNameError,
            DocumentNotFoundError,
            FileAlreadyExistsError,
            FolderAlreadyExistsError,
            NoDraftError,
            AuthRequiredError,
            GoogleApiError,
            PermissionDeniedError,
        ]
        for cls in subclasses:
            assert issubclass(cls, InkClerkError), f"{cls.__name__} must subclass InkClerkError"

    def test_all_subclasses_are_exceptions(self):
        assert issubclass(InkClerkError, Exception)
