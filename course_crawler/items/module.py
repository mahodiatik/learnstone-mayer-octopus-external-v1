from typing import Optional

from pydantic import BaseModel


class Module(BaseModel):
    type: Optional[str]
    title: Optional[str]
    link: Optional[str]
