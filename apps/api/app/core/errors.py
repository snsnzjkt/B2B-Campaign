class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: dict | None = None):
        super().__init__(code="not_found", message=message, status_code=404, details=details)


class InvalidCredentialsError(AppError):
    def __init__(self):
        super().__init__(code="invalid_credentials", message="Invalid email or password", status_code=401)


class TokenExpiredError(AppError):
    def __init__(self):
        super().__init__(code="token_expired", message="Token has expired", status_code=401)


class InvalidTokenError(AppError):
    def __init__(self):
        super().__init__(code="invalid_token", message="Token is invalid", status_code=401)


class ConflictError(AppError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(code="conflict", message=message, status_code=409, details=details)
