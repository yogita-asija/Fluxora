from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class LiveStatus(BaseModel):
    status: str


class ReadyStatus(BaseModel):
    status: str
    checks: dict[str, str]
