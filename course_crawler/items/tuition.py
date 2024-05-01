from typing import Optional

from pydantic import BaseModel


class Tuition(BaseModel):
    study_mode: Optional[str]
    duration: Optional[str]
    student_category: Optional[str]
    fee: Optional[str]
