from typing import Optional

from pydantic import BaseModel


class Location(BaseModel):
    value: Optional[str]
