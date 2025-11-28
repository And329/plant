from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    locale: str | None = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format (allow .local for development)."""
        if '@' not in v or len(v.split('@')) != 2:
            raise ValueError('Invalid email format')
        return v.lower()


class UserLogin(BaseModel):
    email: str
    password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate email format (allow .local for development)."""
        if '@' not in v or len(v.split('@')) != 2:
            raise ValueError('Invalid email format')
        return v.lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    locale: str | None
