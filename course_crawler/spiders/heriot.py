from datetime import datetime
import os
import re
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs
from bs4 import BeautifulSoup, Tag
import scrapy
from scrapy import signals
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy.http import HtmlResponse


class HeriotSpider(scrapy.Spider):
    name = "heriot"
    # allowed_domains = ["*.hw.ac.uk"]
    output_path = (
        os.path.join("..", "data", "courses", "output")
        if os.getcwd().endswith("spiders")
        else os.path.join("course_crawler", "data", "courses", "output")
    )

    # Overrides configuration values defined in course_crawler/settings.py
    custom_settings = {
        "FEED_URI": Path(
            f"{output_path}/{name}/"
            f"{name}_graduate_courses_{datetime.today().strftime('%Y-%m-%d')}.json"
        )
    }
    pattern_ielts = re.compile(r"IELTS\s\d+(\.\d+)?")
    pattern_toefl = re.compile(r"TOEFL\s\d+(\.\d+)?")
    pattern_date = re.compile(
        r"\b\d{1,2}\s(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{4}\b"
    )

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(HeriotSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        return spider

    def spider_opened(self):
        output_path = (
            os.path.join("..", "data", "courses", "output")
            if os.getcwd().endswith("spiders")
            else os.path.join("course_crawler", "data", "courses", "output")
        )
        Path(f"{output_path}/{self.name}").mkdir(parents=True, exist_ok=True)

    def start_requests(self):
        url = "https://search.hw.ac.uk/s/search.html?gscope1=uk%2Conline%7C&profile=programmes&f.Level%7Clevel=Postgraduate&collection=heriot-watt%7Esp-programmes"
        yield scrapy.Request(
            url,
            callback=self.parse,
            meta=dict(
                playwright=True,
                playwright_include_page=True,
                errback=self.errback,
            ),
        )

    def parse(self, response: HtmlResponse):
        # page = response.meta["playwright_page"]
        # await page.close()
        soup = BeautifulSoup(response.body, "html.parser", from_encoding="utf-8")
        courses = self._get_courses(soup)
        for course in courses:
            course_name = self._get_course_name(course)
            qualification = self._get_qualification(course)

            search_link = self._get_search_link(response, course)
            level = self._get_level(course)
            delivery = self._get_all_deliveries(course)
            location = self._get_location(course)

            if search_link:
                query = parse_qs(search_link)
                course_link = next(iter(query["url"]), None)
                if course_link:
                    yield scrapy.Request(
                        course_link,
                        callback=self._parse_course_details_with_soup,
                        meta=dict(
                            playwright=True,
                            playwright_include_page=True,
                            errback=self.errback,
                            course_name=course_name,
                            course_link=course_link,
                            level=level,
                            delivery=delivery,
                            location=location,
                            qualification=qualification,
                        ),
                    )

        next_page = self._get_next_page(soup)

        if next_page:
            print(next_page)
            yield scrapy.Request(
                response.urljoin(next_page),
                meta=dict(
                    playwright=True,
                    playwright_include_page=True,
                    errback=self.errback,
                ),
            )

    def _get_next_page(self, soup):
        try:
            return soup.select_one(
                ".hw_course-search__pagination-link.hw_course-search__pagination-link--next"
            ).get("href")
        except:
            return None

    def _get_courses(self, soup: BeautifulSoup):
        return soup.select("table .clickable")

    def _get_location(self, course: Tag):
        try:
            return course.select_one(".hw_course-search__location").get_text().strip()
        except:
            return ""

    def _get_all_deliveries(self, course: Tag) -> List[str]:
        return [
            delivery.strip()
            for delivery in course.select_one(".hw_course-search__delivery")
            .get_text(separator="\n")
            .strip()
            .split("\n")
            if delivery.strip() != ""
        ]

    def _get_level(self, course: Tag):
        try:
            return course.select_one(".hw_course-search__level").get_text().strip()
        except:
            return ""

    def _get_search_link(self, response: HtmlResponse, course: Tag):
        return response.urljoin(
            course.select_one(".hw_course-search__subject a").get("href")
        )

    def _get_qualification(self, course: Tag):
        return (
            course.select_one(".hw_course-search__subject a")
            .contents[-1]
            .get_text()
            .replace(">", "")
            .strip()
        )

    def _get_course_name(self, course: Tag):
        try:
            return (
                course.select_one(".hw_course-search__subject a strong")
                .get_text()
                .strip()
            )
        except:
            return ""

    async def _parse_course_details_with_soup(self, response: HtmlResponse):
        page = response.meta["playwright_page"]
        await page.close()
        soup = BeautifulSoup(response.body, "html.parser", from_encoding="utf-8")
        meta_data = self._get_meta_data(soup)

        about = self._get_about(soup)
        courses = self._get_all_courses(soup)
        description = self._get_description(soup)
        start_dates = self._get_start_dates(soup)
        application_dates = self._get_application_dates(soup)
        university_name = self._get_university_name(soup)
        entry_requirements = self._get_entry_requirements(soup)
        language_requirements = self._get_language_requirements(soup)
        tuitions = self._get_tutions(soup, meta_data)

        yield {
            "title": response.meta["course_name"],
            "link": response.meta["course_link"],
            "study_level": response.meta["level"],
            "locations": [{"value": response.meta["location"]}],
            "about": about,
            "start_dates": start_dates,
            "application_dates": application_dates,
            "description": description,
            "university_title": university_name,
            "qualification": response.meta["qualification"],
            "tuitions": tuitions,
            "entry_requirements": entry_requirements,
            "language_requirements": language_requirements,
            "modules": courses,
        }

    def _get_start_dates(self, soup: BeautifulSoup):
        start_dates = soup.select_one('dt:contains("Start date") + dd')
        return (
            [{"value": date.strip()} for date in start_dates.text.strip().split(",")]
            if start_dates
            else []
        )

    def _get_application_dates(self, soup: BeautifulSoup):
        try:
            overview = soup.select_one("#overview").get_text().strip()
            if overview:
                return (
                    [{"value": date} for date in self.pattern_date.findall(overview)]
                    if overview
                    else []
                )
            return []
        except:
            return []

    def _get_tutions(self, soup: BeautifulSoup, meta_data: Dict[str, str]):
        try:
            tuitions = []
            tuition_table = soup.select_one("table.hw-content-blocks__table")
            if tuition_table:
                study_modes = [
                    x.get_text().strip().split("\n")[0]
                    for x in tuition_table.select("thead tr th")
                    if x.get_text().strip() != "" and x.get_text().find("Status") == -1
                ]
                rows = tuition_table.select("tbody tr")
                for row in rows:
                    category = row.select_one("th").get_text().strip().split("\n")[0]
                    fees = [fee.get_text().strip() for fee in row.select("td")]
                    for study_mode, fee in zip(study_modes, fees):
                        tuitions.append(
                            {
                                "student_category": category,
                                "fee": fee,
                                "study_mode": study_mode,
                                "duration": meta_data["Duration"]
                                if "Duration" in meta_data
                                else "",
                            }
                        )
            return tuitions
        except:
            return []

    def _get_language_requirements(self, soup: BeautifulSoup):
        try:
            language_requirements = []
            try:
                ielts = [
                    {
                        "language": "English",
                        "score": self.pattern_ielts.search(l.get_text().strip()).group(0),
                        "test": "IELTS",
                    }
                    for l in soup.select("#entry-requirements p")
                    if "IELTS" in l.get_text().strip()
                ]
            except:
                ielts = []

            try:
                toefl = [
                    {
                        "language": "English",
                        "score": self.pattern_toefl.search(l.get_text().strip()).group(
                            0
                        ),
                        "test": "TOEFL",
                    }
                    for l in soup.select("#entry-requirements p")
                    if "TOEFL" in l.get_text().strip()
                ]
            except:
                toefl = []
            if len(ielts) > 0:
                language_requirements.append(ielts[0])
            if len(toefl) > 0:
                language_requirements.append(toefl[0])
            return language_requirements
        except:
            return []

    def _get_entry_requirements(self, soup: BeautifulSoup):
        try:
            return (
                soup.find(id="entry-requirements").prettify().strip().replace("\n", "")
                if soup.find(id="entry-requirements")
                else ""
            )
        except:
            return ""

    def _get_university_name(self, soup: BeautifulSoup):
        try:
            return soup.find(id="logoLabel").get_text().strip()
        except:
            return ""

    def _get_description(self, soup: BeautifulSoup):
        try:
            description = soup.select_one("div.pb-5 p")
            return description.get_text().strip() if description else ""
        except:
            return ""

    def _get_all_courses(self, soup: BeautifulSoup):
        try:
            courses = []
            for course in soup.select(
                "#course-content .tab-switcher__tab .rte-container ul"
            ):
                type = course.find_previous(["h3", "h4", "h5", "h6", "p"])
                if type:
                    type = type.get_text().strip()
                    if type.lower().find("option") != -1:
                        type = "Optional"
                    elif type.lower().find("core") != -1:
                        type = "Core"
                    elif type.lower().find("compulsory") != -1:
                        type = "Compulsory"
                    elif type.lower().find("project") != -1:
                        type = "Project"
                    else:
                        type = "Mandatory"
                else:
                    type = "Mandatory"
                for li in course.select("li"):
                    if li.get_text().replace("\n", "").strip() != "":
                        courses.append(
                            {
                                "title": li.get_text()
                                .replace("\n", "")
                                .split(":")[0]
                                .strip(),
                                "type": type,
                                "link": "",
                            }
                        )
            return courses
        except Exception as e:
            return []

    def _get_about(self, soup: BeautifulSoup):
        try:
            return soup.select_one("div.pb-5").prettify().strip().replace("\n", "")
        except:
            return ""

    def _get_meta_data(self, soup: BeautifulSoup):
        meta_data = {}

        for dt, dd in zip(soup.select("dl dt"), soup.select("dl dd")):
            key = dt.get_text().strip()  # Extract text and remove extra spaces
            value = dd.get_text().strip()  # Extract text and remove extra spaces
            meta_data[key] = value
        return meta_data

    async def errback(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()


if __name__ == "__main__":
    cp = CrawlerProcess(get_project_settings())

    cp.crawl(HeriotSpider)
    cp.start()