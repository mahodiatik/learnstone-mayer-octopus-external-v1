from typing import Optional

from pydantic import BaseModel


class Date(BaseModel):
    value: Optional[str]
