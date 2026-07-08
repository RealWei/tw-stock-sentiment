"""history.csv 讀寫。長表格式：date,indicator,value。"""

import csv
from collections import defaultdict


def load_history(path):
    """回傳 {indicator: [(date, value), ...]}，依日期排序。"""
    series = defaultdict(dict)
    if not path.exists():
        return {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            series[row["indicator"]][row["date"]] = float(row["value"])
    return {
        ind: sorted(by_date.items())
        for ind, by_date in series.items()
    }


def upsert(path, indicator, points):
    """寫入 (date, value) 列表，同 indicator 同日期覆蓋。"""
    history = load_history(path)
    by_date = dict(history.get(indicator, []))
    for date, value in points:
        by_date[date] = float(value)
    history[indicator] = sorted(by_date.items())

    with open(path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["date", "indicator", "value"])
        for ind in sorted(history):
            for date, value in history[ind]:
                writer.writerow([date, ind, value])
