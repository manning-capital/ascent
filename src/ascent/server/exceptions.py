class AscentAPIError(Exception):
    """Base for all API errors.

    Raise this (or a subclass) anywhere in service or router code.
    The global exception handler in main.py catches it and returns
    a standardised JSON envelope.
    """

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(AscentAPIError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(404, "not_found", message)


class ConflictError(AscentAPIError):
    def __init__(self, message: str = "Resource already exists"):
        super().__init__(409, "conflict", message)


class BadRequestError(AscentAPIError):
    def __init__(self, message: str = "Bad request"):
        super().__init__(400, "bad_request", message)
