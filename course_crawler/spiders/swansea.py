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
from scrapy_playwright.page import PageMethod

class SwanseaSpider(scrapy.Spider):
    name = "swansea"
    university="Swansea University"
    study_level = "Graduate"
    start_urls = [
        'https://www.swansea.ac.uk/postgraduate/taught/'
    ]
    ielts_equivalent_score={}
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
    default_application_dates= []
    ielts_pattern=re.compile(r"IELTS.*?(\d+\.\d+|\d+)")
    toefl_pattern=re.compile(r"TOEFL.*?(\d+\.\d+|\d+)")
    application_dates_pattern=re.compile(r"(\d{1,2}\s(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{4})")
    start_date_pattern=re.compile(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{4}\b(?:\sor\s\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{4}\b)?|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{4}\b')
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(SwanseaSpider, cls).from_crawler(crawler, *args, **kwargs)
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
        language_url="https://www.swansea.ac.uk/admissions/english-language-requirements/approved-tests-for-nationals-of-any-country/#d.en.19635"
        yield scrapy.Request(
            language_url,
            callback=self.parse_english_language_requirements
        )
        application_dates_url="https://www.swansea.ac.uk/admissions/application-deadlines/"
        yield scrapy.Request(
            application_dates_url,
            callback=self.parse__default_application_dates
        )
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta=dict(
                    course_link=url,
                    playwright=True,
                    playwright_include_page=True,
                    errback=self.errback,
                ),
            )
        industry_courses_url="https://www.swansea.ac.uk/science-and-engineering/courses/engineering/msc-industry/"
        yield scrapy.Request(
            industry_courses_url,
            callback=self.parse_industry_courses,
        )
        
    
    def parse_english_language_requirements(self,response: HtmlResponse):
        soup= BeautifulSoup(response.body,"html.parser", from_encoding="utf-8")
        ielts_equivalent = {"6.0": [], "6.5": [], "7.0": []}  # Initialize the lists

        table = soup.select_one("table.mceItemTable")

        for i in range(1, 4):
            for row in table.select("tr"):
                cells = row.select("td")
                language = "English"
                test = cells[0].text.strip()
                score = cells[i].text.strip()
                if score.find("Equivalent to IELTS") != -1:
                    continue
                if(score!=""):
                    if i == 1:
                        ielts_equivalent["6.0"].append({"language": language, "test": test, "score": score})
                    elif i == 2:
                        ielts_equivalent["6.5"].append({"language": language, "test": test, "score": score})
                    elif i == 3:
                        ielts_equivalent["7.0"].append({"language": language, "test": test, "score": score})
        self.ielts_equivalent_score=ielts_equivalent

    def parse__default_application_dates(self,response: HtmlResponse):
        soup= BeautifulSoup(response.body,"html.parser", from_encoding="utf-8")
        ok=soup.select_one("#d\.en\.163697 h2").find_next("table")
        for i in ok.find_all("td"):
            text=i.text
            date_pattern = re.compile(r"(\d{1,2})\s*(?:st|nd|rd|th)?\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{4})")
            match = date_pattern.search(text)
            if match:
                self.default_application_dates.append({"value": match.group(0)})


    async def parse(self, response: HtmlResponse):
        page = response.meta["playwright_page"]
        await page.close()
        soup = BeautifulSoup(response.body, "html.parser", from_encoding="utf-8")
        courses=soup.select("#app li a")
        for course in courses:
            link=course.get("href")
            title=self._get_title(course)
            qualification=self._get_qualification(course)
            if link:
                # query=parse_qs(link)
                # course_link=next(iter(query["url"],None))
                course_link=link
                if course_link:
                    yield scrapy.Request(
                        course_link,
                        callback=self.parse_course,
                        meta=dict(
                            playwright=True,
                            playwright_include_page=True,
                            errback=self.errback,
                            course_link=course_link,
                            title=title,
                            qualification=qualification,
                        )
                    )
    
    def parse_industry_courses(self,response: HtmlResponse):
        soup = BeautifulSoup(response.body, "html.parser", from_encoding="utf-8")
        courses= soup.select("a.su-image")
        for course in courses:
            if(course["href"].find("youtu.be")==-1):
                course_link = course["href"]
                course_link = "https://www.swansea.ac.uk" + course_link
                title= course.text.strip()
                qualification ="MSc"
                yield scrapy.Request(
                    course_link,
                    callback=self.parse_course,
                    meta=dict(
                        playwright=True,
                        playwright_include_page=True,
                        errback=self.errback,
                        course_link=course_link,
                        title=title,
                        qualification=qualification,
                    )
                )
                
    async def parse_course(self, response: HtmlResponse):
        page = response.meta["playwright_page"]
        await page.close()
        soup = BeautifulSoup(response.body, "html.parser", from_encoding="utf-8")
        description = self._get_description(soup)
        university_title = self.university
        application_dates=self._get_application_dates(soup)
        entry_requirements=self._get_entry_requirements(soup)
        language_requirements=self._get_english_language_requirements(soup)
        study_level= self.study_level
        about=self._get_about(soup)
        qualifications = response.meta["qualification"]
        qualification_pattern = r'\b(MSc|PGCert|PGDip|MA|MBA|MPhil|LLM|PhD|EdD|JD|MSW|MPA|MPAS|MAcc|EMBA|MFA|MD|PsyD|DPT|DBA|DEng|DSc|DSW|DDS|MBBCh)\b'
        matches = re.findall(qualification_pattern, qualifications)
        for qualification in matches:
            qualification=qualification.strip()
            start_dates=self._get_start_dates(soup,qualification)
            modules=self._get_modules(soup,qualification,len(matches)>1)
            tuitions=self._get_tuitions(soup,qualification)
            locations=self._get_locations(soup,qualification)
            if response.meta["course_link"].find("erasmus-mundas")!=-1 or response.meta["course_link"].find("walesdtp")!=-1 or response.meta["course_link"].find("academic-partnerships")!=-1 or response.meta["course_link"]=="https://www.swansea.ac.uk/engineering/courses/postgraduate/msc-industry/":
                pass
            else:
                yield {
                    "title": response.meta["title"],
                    "link": response.meta["course_link"],
                    "study_level": study_level,
                    "qualification": qualification,
                    "university_title": university_title,
                    "locations": locations,
                    "description": description,
                    "about": about,
                    "application_dates": application_dates,
                    "start_dates": start_dates,
                    "entry_requirements": entry_requirements,
                    "modules":modules,
                    "tuitions":tuitions,
                    "language_requirements":language_requirements,
                }

    
    def _get_title(self, course: Tag):
        try:
            title= course.text.strip()
        except:
            title=""
        return title
    
    def _get_qualification(self, course: Tag):
        try:
            qualification=course.text.strip()
        except AttributeError:
            qualification=""
        return qualification
    
    def _get_description(self, course: Tag):
        try:
            description= course.select_one(".featured-course-content-content-pods p").text.strip()
        except AttributeError:
            description=""
        return description
    
        
    def _get_about(self, course: Tag):
        try:
            about= course.select_one(".featured-course-content-content-pods .featured-course-content-content-pods").prettify()
        except AttributeError:
            about=""
        return about


    def _get_entry_requirements(self, course: Tag):
        try:
            entry_requirements= course.select_one("#entry-requirements").prettify()
        except AttributeError:
            try:
                entry_requirements= course.select_one("div #gofynion-mynediad-contents").prettify()
            except AttributeError:
                entry_requirements=""
        return entry_requirements
    

    
    def _get_locations(self, course: Tag,qualification: str):
        try:
            locations=[]
            location_set=set()
            location_table=course.select(".tab-content dl dt")
            for values in location_table:
                if(values.text.strip().lower().find("location")!=-1 or values.text.strip().lower().find("lleoliad")!=-1):
                    qualification_checker=values.find_previous("a",class_="featured-course-content-accordion-link").text.strip().lower()
                    if(qualification_checker.find(qualification.lower())!=-1):
                        value=values.findNext("dd").text.strip()
                        location_set.add(value)
            for location in location_set:
                locations.append({"value":location})
        except AttributeError:
            locations = []
        return locations
        
    
    
    def _get_start_dates(self, soup: BeautifulSoup,qualification: str):
        try:
            start_dates = []
            start_date_set=set()
            dates_data=soup.select(".featured-course-content-key-details td")
            for dates in dates_data:
                if(re.search(self.start_date_pattern, dates.text.strip()) is not None):
                    qualification_checker=dates.find_previous("a",class_="featured-course-content-accordion-link").text.strip().lower()
                    if(qualification_checker.find(qualification.lower())!=-1):
                        date=re.search(self.start_date_pattern, dates.text.strip()).group(0)
                        start_date_set.add(date)
            for date in start_date_set:
                start_dates.append({"value":date})     
        except (IndexError, AttributeError):
             start_dates= []
        return start_dates
    
    def _get_application_dates(self, soup: BeautifulSoup):
        try:
            application_dates = []
            application_text=soup.select_one("#application-deadlines").text
            if(re.search(self.application_dates_pattern, application_text) is not None):
                date = re.search(self.application_dates_pattern, application_text).group(0)
                application_dates.append({"value":date})
            else:
                application_dates=self.default_application_dates #as standard application dates for postgraduate taught courses are described in https://www.swansea.ac.uk/admissions/application-deadlines/
        except AttributeError:
                application_dates=self.default_application_dates #as standard application dates for postgraduate taught courses are described in https://www.swansea.ac.uk/admissions/application-deadlines/
        return application_dates
    
    
    
    
        
    def _get_modules(self, soup: BeautifulSoup,qualification: str,multiple):
        try:
            modules=[]
            subjects=soup.select(".ppsm-ms-moduleTitle a")
            for subject in subjects:
                try:
                    selector=subject.find_previous("div",_class="variant")
                    qualification_checker=selector.select_one("h3").text.strip().lower()
                    if(qualification_checker.find(qualification.lower())!=-1):
                        title=subject.text.strip()
                        link=subject.get("href")
                        if(subject.findPrevious("h5").text.lower().find("optional")!=-1):
                            type="Optional"
                        elif(subject.findPrevious("h5").text.lower().find("compulsory")!=-1):
                            type="Compulsory"
                        elif(subject.findPrevious("h5").text.lower().find("core")!=-1):
                            type="Core"
                        else:
                            type="Compulsory"
                        degree=subject.find_previous("h3").text.strip()
                        if(multiple):
                            if(title!=""):
                                if degree.lower().find(qualification.lower())!=-1:
                                    modules.append({"title":title,"link":link,"type":type})
                                elif degree.lower().find("modules")!=-1:
                                    modules.append({"title":title,"link":link,"type":type})
                        elif(title!=""):
                            modules.append({"title":title,"link":link,"type":type})
                except AttributeError:
                    title=subject.text.strip()
                    link=subject.get("href")
                    if(subject.findPrevious("h5").text.lower().find("optional")!=-1):
                        type="Optional"
                    elif(subject.findPrevious("h5").text.lower().find("compulsory")!=-1):
                        type="Compulsory"
                    elif(subject.findPrevious("h5").text.lower().find("core")!=-1):
                        type="Core"
                    else:
                        type="Compulsory"
                    degree=subject.find_previous("h3").text.strip()
                    if(multiple):
                        if(title!=""):
                            if degree.lower().find(qualification.lower())!=-1:
                                modules.append({"title":title,"link":link,"type":type})
                            elif degree.lower().find("modules")!=-1:
                                modules.append({"title":title,"link":link,"type":type})
                    elif(title!=""):
                        modules.append({"title":title,"link":link,"type":type})
                    
        except AttributeError:
            return []
        return modules
    

        
    def _get_tuitions(self, soup: BeautifulSoup,qualification: str):
        try:
            tuitions=[]
            tuition_uks=soup.select("#accordion-uk .card")
            for tuition_uk in tuition_uks:
                student_category="UK"
                data=tuition_uk.select_one(".card-header a").text.strip()
                mode_pattern = re.compile(r'\b(Full|Part|Llawn|Rhan)\s*(Time|Amser)\b')
                study_mode=mode_pattern.search(data).group(0)
                duration_pattern= re.compile(r'\b\d+(\.\d+)?\s*(Blwyddyn|Year|Years|Blynedd|Month|Months)\b')
                duration=duration_pattern.search(data).group(0)
                for fees in tuition_uk.select("td"):
                    if(fees.text.strip().find("£")!=-1):
                        fee=fees.text.strip()
                        qualification_checker=fees.find_previous("a",class_="featured-course-content-accordion-link").text.strip().lower()
                        if(qualification_checker.find(qualification.lower())!=-1):
                            tuitions.append({"student_category":student_category,"study_mode":study_mode,"duration":duration,"fee":fee})
                    elif(fees.text.strip().find("NHS")!=-1):
                        fee=fees.text.strip()
                        qualification_checker=fees.find_previous("a",class_="featured-course-content-accordion-link").text.strip().lower()
                        if(qualification_checker.find(qualification.lower())!=-1):
                            tuitions.append({"student_category":student_category,"study_mode":study_mode,"duration":duration,"fee":fee})
            tuition_ints=soup.select("#accordion-int .card")
            for tuition_int in tuition_ints:
                student_category="International"
                data=tuition_int.select_one(".card-header a").text.strip()
                mode_pattern = re.compile(r'\b(Full|Part|Llawn|Rhan)\s*(Time|Amser)\b')
                study_mode=mode_pattern.search(data).group(0)
                duration_pattern= re.compile(r'\b\d+(\.\d+)?\s*(Blwyddyn|Year|Years|Blynedd|Month|Months)\b')
                duration=duration_pattern.search(data).group(0)
                for fees in tuition_int.select("td"):
                    if(fees.text.strip().find("£")!=-1):
                        fee=fees.text.strip()
                        qualification_checker=fees.find_previous("a",class_="featured-course-content-accordion-link").text.strip().lower()
                        if(qualification_checker.find(qualification.lower())!=-1):
                            tuitions.append({"student_category":student_category,"study_mode":study_mode,"duration":duration,"fee":fee})
                    elif(fees.text.strip().find("NHS")!=-1):
                        fee=fees.text.strip()
                        qualification_checker=fees.find_previous("a",class_="featured-course-content-accordion-link").text.strip().lower()
                        if(qualification_checker.find(qualification.lower())!=-1):
                            tuitions.append({"student_category":student_category,"study_mode":study_mode,"duration":duration,"fee":fee})
        except AttributeError:
            tuitions = []
        return tuitions
    
    def _get_english_language_requirements(self, soup: BeautifulSoup):
        try:
            language_requirements = []
            language=soup.select_one("#entry-requirements").text
            if(re.search(self.ielts_pattern, language) is not None):
                score = re.search(self.ielts_pattern, language).group(1)
                if(score=="7"):
                    score="7.0"
                language_requirements=self.ielts_equivalent_score[score]
            if(re.search(self.toefl_pattern, language) is not None):
                score = re.search(self.toefl_pattern, language).group(1)
                language_requirements.append({"language":"English","test":"TOEFL","score":score})  
        except AttributeError:
            language_requirements = []
        return language_requirements
    
    async def errback(self, failure):
        page = failure.request.meta["playwright_page"]
        await page.close()
       

if __name__ == "__main__":
    cp = CrawlerProcess(get_project_settings())

    cp.crawl(SwanseaSpider)
    cp.start()