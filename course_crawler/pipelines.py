# Define your item pipelines here
#
# Don"t forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import os
import logging

from functional import seq

from course_crawler.items.course import Course
from course_crawler.items.location import Location
from course_crawler.items.date import Date
from course_crawler.items.language_requirement import LanguageRequirement
from course_crawler.items.module import Module
from course_crawler.items.tuition import Tuition


class SaveCourseToJSON(object):

    def process_item(self, item, spider):
        assert (set(item.keys()).issubset(set(Course.__fields__.keys())))

        locations = seq(item["locations"]) \
            .map(lambda x: Location(value=x)) \
            .to_list()

        start_dates = seq(item["start_dates"]) \
            .map(lambda x: Date(value=x)) \
            .to_list()

        application_dates = seq(item["application_dates"]) \
            .map(lambda x: Date(value=x)) \
            .to_list()

        language_requirements = seq(item["language_requirements"]) \
            .map(lambda x: LanguageRequirement(language=x["language"],
                                               test=x["test"],
                                               score=x["score"])) \
            .to_list()

        modules = seq(item["modules"]) \
            .map(lambda x: Module(type=x["type"],
                                  title=x["title"],
                                  link=x["link"])) \
            .to_list()

        tuitions = seq(item["tuitions"]) \
            .map(lambda x: Tuition(study_mode=x["study_mode"],
                                   duration=x["duration"],
                                   student_category=x["student_category"],
                                   fee=x["fee"])) \
            .to_list()

        course = Course(**{
            **item,
            "locations": locations,
            "start_dates": start_dates,
            "application_dates": application_dates,
            "language_requirements": language_requirements,
            "modules": modules,
            "tuitions": tuitions
        })

        return course
