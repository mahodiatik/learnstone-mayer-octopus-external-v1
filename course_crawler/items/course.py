# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html
from typing import Optional

from pydantic import BaseModel

from .location import Location
from .date import Date
from .language_requirement import LanguageRequirement
from .module import Module
from .tuition import Tuition


class Course(BaseModel):
    link: Optional[str] #found
    title: str #found
    study_level: Optional[str] #found
    qualification: Optional[str] #found
    university_title: str #found
    locations: list[Location] #found
    description: Optional[str] #found
    about: Optional[str] #found
    start_dates: list[Date] #found
    application_dates: list[Date] #NA
    entry_requirements: Optional[str] #found
    language_requirements: list[LanguageRequirement] #found
    modules: list[Module] #found
    tuitions: list[Tuition] #found
