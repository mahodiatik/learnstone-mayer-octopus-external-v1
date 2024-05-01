import json
import re
from glob import glob
from pathlib import Path
from copy import deepcopy
from datetime import datetime

import numpy as np
import pandas as pd
from functional import seq


if __name__ == "__main__":
    course_archive = {}
    for path in glob("../data/courses/output/**/*.json"):
        university = path.split('/')[-2]

        if university in course_archive:
            course_archive[university].append(path)
        else:
            course_archive[university] = [path]

    simple_attrs = ['link', 'title', 'study_level', 'qualification', 'university_title',
                    'description', 'about', 'entry_requirements']
    complex_attrs = ['locations', 'start_dates', 'application_dates']
    nested_attrs = {
        'tuitions': ['study_mode', 'duration', 'student_category', 'fee'],
        'language_requirements': ['language', 'test', 'score'],
        'modules': ['type', 'title', 'link']
    }

    data = []
    for university, courses_paths in course_archive.items():
        for course_path in courses_paths:
            version = re.findall(r'\d+-\d+-\d+', course_path).pop()
            try:
                with open(course_path, 'r') as f:
                    courses = json.load(f)

                courses_df = pd.DataFrame(courses)

                for attr in simple_attrs + complex_attrs:
                    courses_df[attr] = courses_df[attr].apply(lambda x: 1 if x else 0)
                for attr in nested_attrs.keys():
                    for child_attr in nested_attrs[attr]:
                        courses_df[f"{attr[:-1]}__{child_attr}"] = courses_df[attr]\
                            .apply(lambda x: sum([1 if item[child_attr] else 0 for item in x]))

                    courses_df[attr] = courses_df[attr].apply(lambda x: len(x))

                for attr in simple_attrs + complex_attrs:
                    data.append({
                        'university': university,
                        'version': version,
                        'attribute': attr,
                        'count': len(courses_df[attr]),
                        'nan_count': (courses_df[attr] == 0).sum(),
                        'nan_perc': ((courses_df[attr] == 0).sum() / len(courses_df)) * 100
                    })

                for attr in nested_attrs.keys():
                    data.append({
                        'university': university,
                        'version': version,
                        'attribute': attr,
                        'count': len(courses_df[courses_df[attr] > 0]),
                        'nan_count': (courses_df[attr] == 0).sum(),
                        'nan_perc': ((courses_df[attr] == 0).sum() / len(courses_df[attr])) * 100
                    })

                    for child_attr in nested_attrs[attr]:
                        child_attr = f"{attr[:-1]}__{child_attr}"

                        count = sum(courses_df[attr])
                        nan_count = seq(zip(courses_df[(courses_df[attr] > 0)][attr],
                                            courses_df[(courses_df[attr] > 0)][child_attr]))\
                            .map(lambda x: x[0] - x[1])\
                            .sum()

                        data.append({
                            'university': university,
                            'version': version,
                            'attribute': child_attr,
                            'count': count,
                            'nan_count': nan_count if count else -1,
                            'nan_perc': (nan_count / count) * 100 if count else 100
                        })
            except KeyError as e:
                print("Exception while parsing %s" % course_path)
                print(e)
            except json.decoder.JSONDecodeError as e:
                print("Exception while parsing %s" % course_path)
                print(e)

    df = pd.DataFrame(data)
    today = datetime.today().strftime('%Y-%m-%d')
    Path(f"data/{today}").mkdir(parents=True, exist_ok=True)

    df = df.sort_values(by=['university', 'version'], ascending=True)
    df.to_csv(f"data/{today}/university_review_stats_{today}.csv", index=False)
