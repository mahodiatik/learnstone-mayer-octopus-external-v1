from typing import Optional

from pydantic import BaseModel


class LanguageRequirement(BaseModel):
    language: Optional[str] = 'English'
    test: Optional[str]
    score: Optional[str]
