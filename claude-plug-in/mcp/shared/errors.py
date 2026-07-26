class InkClerkError(Exception):
    code: str = "INTERNAL_ERROR"

    def to_dict(self) -> dict:
        return {"error": self.code, "message": str(self)}


class ProjectNotFoundError(InkClerkError):
    code = "PROJECT_NOT_FOUND"


class AmbiguousProjectNameError(InkClerkError):
    code = "AMBIGUOUS_PROJECT_NAME"


class DocumentNotFoundError(InkClerkError):
    code = "FILE_NOT_FOUND"


class FileAlreadyExistsError(InkClerkError):
    code = "FILE_ALREADY_EXISTS"


class FolderAlreadyExistsError(InkClerkError):
    code = "FOLDER_ALREADY_EXISTS"


class NoDraftError(InkClerkError):
    code = "NO_DRAFT"


class AuthRequiredError(InkClerkError):
    code = "AUTH_REQUIRED"


class GoogleApiError(InkClerkError):
    code = "GOOGLE_API_ERROR"


class PermissionDeniedError(InkClerkError):
    code = "PERMISSION_DENIED"
