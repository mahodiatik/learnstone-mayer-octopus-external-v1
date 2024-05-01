from datetime import datetime
import json
import os
import re
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs
from bs4 import BeautifulSoup, Tag

import requests

def _get_duration(soup: BeautifulSoup) -> list[dict]: 
    try:
        durations = {}

        duration_text = soup.select_one("span.fa.fa-pencil-square-o").next_sibling.get_text().strip()

        pattern = r'(?:(?P<qualification>\w+(\s+with\s+field\s+dissertation)?)\s*:\s*)?(?P<duration>\d+)\s+months\s+(?P<study_mode>\w+-time)'

        matches = re.finditer(pattern, duration_text)

        for match in matches:
            qualification = match.group('qualification')
            if qualification is None:
                qualification = ''
            duration = match.group('duration')
            study_mode = match.group('study_mode')
            qualification_info = { 'duration': duration +" months", 'study_mode': study_mode}
            durations[qualification] = qualification_info
    except:
        durations = {}
    return durations

def _get_tuitions(soup: BeautifulSoup, parsed_qualification: str, multiple: bool):
    try:
        tuitions=[]
        try:
            duration_text=soup.select_one("span.fa.fa-pencil-square-o").next_sibling.get_text().strip()
        except:
            duration_text = ''
        # print(duration_text)
        mode_pattern = r'(full[- ]?time|part[- ]?time)'
        try:
            study_mode = re.search(mode_pattern, duration_text,re.IGNORECASE).group(0)
        except:
            study_mode = "Full-time"
        # print(study_mode)
        # duration_pattern = r'(?:\b(one|two|three|four|five|six|seven|eight|nine|ten)\b|\d+)\s+(?:months?|years?)'
        duration_pattern = r'(?:\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\b)\s+(week|weeks|month|months|year|years)'
        try:
            duration = re.search(duration_pattern, duration_text,re.IGNORECASE).group(0)
        except:
            duration = ""

        #TODO process durations from here.
        durations = _get_duration(soup)

        fee_pattern = r'[£€]([\d,]+)'
        tuition_table = soup.select_one('div.tab-inner table')
        # print(tuition_table)
        try:
            for i in tuition_table.select('tr'):
                # print(i)
                th = i.select_one("th").text
                if th:
                    fee_pattern = r'£([\d,]+)'
                    for keyword in ["scotland", "england", "international", "strathclyde", "home", "ipgce", "cohort", "internal"]:
                        if keyword in th.lower():
                            # print(keyword)
                            try:
                                category = i.select_one("th").get_text().strip()
                            except AttributeError as e:
                                category = ""

                            # print(category)
                            try:
                                fee_selector = i.select_one("td")
                                # print(fee_selector)
                                try:
                                    list_selector=fee_selector.select("li")
                                    for li in list_selector:
                                        fee_pattern = r'[£€]([\d,]+)'
                                        degree_selector=""
                                        try:
                                            fee = re.search(fee_pattern, li.text).group(0)
                                        except:
                                            fee = ""
                                        if(fee!=""):
                                            try:
                                                degree_selector = li.find_previous("strong").text.strip()
                                            except:
                                                pass
                                            try:
                                                if(degree_selector.lower().find(parsed_qualification.lower()) == -1):
                                                    degree_selector = li.find_previous("h4").text.strip()
                                            except:
                                                pass
                                        if(li.text.lower().find("part-time") != -1):
                                            study_mode="Part-time"
                                        elif(li.text.lower().find("full-time") != -1):
                                            study_mode="Full-time"
                                        if(multiple and fee!=""):
                                            if(degree_selector.lower().find(parsed_qualification.lower()) != -1 or degree_selector.lower().find("2023/24") != -1 or li.text.lower().find(parsed_qualification.lower()) != -1):
                                                tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": durations[parsed_qualification]['duration']})
                                        else:
                                            if(fee!=""):
                                                tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration})
                                except:
                                    pass
                              
                                try:
                                    paragraph=fee_selector.select("p")
                                    for p in paragraph:
                                        # fee_pattern = r'£([\d,]+)'
                                        degree_selector=""
                                        
                                        fee_pattern = r'[£€]([\d,]+)'
                                        try:
                                            fee = re.search(fee_pattern, p.text).group(0)
                                        except:
                                            fee = ""
                                        if(fee!=""):
                                            try:
                                                degree_selector = p.find_previous("strong").text.strip()
                                            except:
                                                pass
                                            try:
                                                if(degree_selector.lower().find(parsed_qualification.lower()) == -1):
                                                    degree_selector = p.find_previous("h4").text.strip()
                                            except:
                                                pass
                                        if(p.text.lower().find("part-time") != -1):
                                            study_mode="Part-time"
                                        elif(p.text.lower().find("full-time") != -1):
                                            study_mode="Full-time"
                                        if(multiple and fee!=""):
                                            if(degree_selector.lower().find(parsed_qualification.lower()) != -1 or degree_selector.lower().find("2023/24") != -1 ):
                                                tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": durations[parsed_qualification]['duration']})
                                            else:
                                                if(fee!=""):
                                                    try:
                                                        text=fee_selector.select_one("strong").text.strip()
                                                        if(text.lower().find("2023/24") != -1 or text.lower().find(parsed_qualification.lower()) != -1):
                                                                tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": durations[parsed_qualification]['duration']})
                                                    except:
                                                        tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration})
                                        else:            
                                            if(fee!=""):
                                                tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration})
                                except:
                                    pass

                            except Exception as e:
                                # print(e)
                                pass
                            break
                    
                    if parsed_qualification.lower() in th.lower() or 'fee' in th.lower():
                        category = "All"
                        cnt = 0
                        try:
                            
                            li = i.select_one("td").select("li")
                            for j in li:
                                try:
                                    fee = re.search(fee_pattern, j.text).group(0)
                                except:
                                    pass
                                if fee:
                                    cnt += 1
                                    tt = j.find_previous('strong')
                                    if tt:
                                        if 'study mode' not in tt.text.lower() and len(tt.text.strip()) > 0:
                                            category = tt.text.strip()
                                        if(category.lower().find("scotland") == -1 and category.lower().find("england") == -1 and category.lower().find("international") == -1 ):
                                            category="All"
                                        tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration})
                                    else:
                                        tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration})
                            if cnt == 0:
                                fee = re.search(fee_pattern, i.select_one("td").text).group(0)
                                if fee:
                                    tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration})
                                
                        except:
                            pass
                        # try:
                        #     fee = re.search(fee_pattern, i.select_one("td").text).group(0)
                        #     tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration}) 
                        # except:
                        #     pass
                    elif 'full-time' in th.lower():
                        category = "All"
                        study_mode = "Full-time"
                        try:
                            fee = re.search(fee_pattern, i.select_one("td").text).group(0)
                            if fee:
                                tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration})
                        except:
                            pass
                    
                    elif 'tuition' in th.lower():
                        fee_selector = i.select_one("td")
                        category="All"
                        try:
                            list=fee_selector.select("li")
                            for li in list:
                                fee_pattern = r'£([\d,]+)'
                                fee = re.search(fee_pattern, li.text).group(0)
                                duration= "1 Year" #as the fees per year is shown in this case
                                if(li.text.lower().find("part-time") != -1):
                                    study_mode="Part-time"
                                elif(li.text.lower().find("full-time") != -1):
                                    study_mode="Full-time"
                                tuitions.append({"student_category": category, "fee": fee, "study_mode": study_mode, "duration": duration})
                        except:
                            pass
        except:
            pass
    except AttributeError:
        return []
    return tuitions

url = 'https://www.strath.ac.uk/courses/postgraduatetaught/appliedtranslationinterpreting/'

response = requests.get(url)
soup = BeautifulSoup(response.content, "html.parser", from_encoding="utf-8")
tuitions = _get_tuitions(soup,"MSc", True)
print(tuitions)

# print(json.dumps(tuitions))
