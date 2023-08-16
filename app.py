import datetime
import json
import logging
import os
from collections import namedtuple
from typing import List, Union

import requests

DEBUG = bool(os.environ.get("DEBUG", False))

if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)

TEMPO_API_BASE = os.environ.get("TEMPO_API_BASE", "https://api.tempo.io/4")
TEMPO_API_WORKLOGS_ENDPOINT = os.environ.get("TEMPO_API_WORKLOGS_ENDPOINT", "/worklogs/user")

HoursLog = namedtuple("HourLog", ["date", "hours"])


def get_start_of_week(within_current_month: bool = True) -> datetime.date:
    today = datetime.date.today()
    last_monday = today - datetime.timedelta(days=today.weekday())
    start_of_month = datetime.date(today.year, today.month, 1)

    if within_current_month:
        return max(last_monday, start_of_month)
    else:
        return last_monday


class LogsSummary:
    hours_by_day: dict

    def __init__(self) -> None:
        self.hours_by_day = {}

    def add_day_hours(self, day: datetime.date, hours: float) -> None:
        self.hours_by_day[day] = self.hours_by_day.get(day, 0) + hours

    def get_total_week_hours(self, within_current_month: bool = True) -> float:
        start_date = get_start_of_week(within_current_month=within_current_month)

        total_hours = 0

        for day in range(start_date.weekday(), 5):
            date = start_date + datetime.timedelta(days=day)
            total_hours += self.hours_by_day.get(date, 0)

        return total_hours

    @property
    def total_month_hours(self) -> float:
        today = datetime.date.today()
        total_hours = 0
        for day in range(1, today.day + 1):
            date = datetime.date(today.year, today.month, day)
            total_hours += self.hours_by_day.get(date, 0)

        return total_hours

    @property
    def working_days_in_month(self) -> int:
        today = datetime.date.today()
        working_days = 0

        for day in range(1, today.day + 1):
            date = datetime.date(today.year, today.month, day)
            if date.weekday() < 5:  # Monday to Friday (0-4 are weekdays)
                working_days += 1

        return working_days

    def get_required_hours_for_week(self, within_current_month: bool = True) -> float:

        if within_current_month:
            today_week_day = min(
                # Day of the week, Monday is 0
                datetime.datetime.today().weekday() + 1,
                # Day of the month, 1-31. If the month started during the week
                # working days.
                datetime.datetime.today().day,
                # Friday. Sat and sunday are not working days.
                5,
            )
        else:
            today_week_day = min(
                # Day of the week, Monday is 0
                datetime.datetime.today().weekday() + 1,
                # Friday (4+1). Sat and sunday are not working days.
                5,
            )

        return today_week_day * 8

    def get_week_work_required_difference(self, within_current_month: bool = True) -> float:
        return self.get_total_week_hours(within_current_month=within_current_month) - self.get_required_hours_for_week(
            within_current_month=within_current_month
        )

    @property
    def required_hours_for_month(self) -> float:
        return self.working_days_in_month * 8

    @property
    def month_work_required_difference(self) -> float:
        return self.total_month_hours - self.required_hours_for_month


class Logger:
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

    @staticmethod
    def log_info(message: str) -> None:
        logging.info(Logger.BLUE + "[INFO] " + message + Logger.RESET)

    @staticmethod
    def log_success(message: str) -> None:
        logging.info(Logger.GREEN + "[SUCCESS] " + message + Logger.RESET)

    @staticmethod
    def log_error(message: str) -> None:
        logging.error(Logger.RED + "[ERROR] " + message + Logger.RESET)

    @staticmethod
    def log_debug(message: str) -> None:
        logging.debug(Logger.YELLOW + "[DEBUG] " + message + Logger.RESET)


def float_to_hours_minutes(value: float) -> str:
    return f"{int(value)}h {int((abs(value) % 1) * 60)}m"


def launch_ui():
    # tempos = get_jira_projects()
    raise Exception("Not implemented")


def cli_main():
    tempos: dict = get_jira_projects()

    summary: LogsSummary = get_total_hours_summary(tempos)

    Logger.log_info("=============Daily Hours=============")
    for day, hours in summary.hours_by_day.items():
        Logger.log_info(f"{day}: {float_to_hours_minutes(hours)}")

    Logger.log_info("=============Week Hours=============")
    Logger.log_info(f"Total Week Hours: {float_to_hours_minutes(summary.get_total_week_hours())}")
    Logger.log_info(
        f"Total Week Hours / required hours : {float_to_hours_minutes(summary.get_total_week_hours())}"
        f" / {float_to_hours_minutes(summary.get_required_hours_for_week())}"
    )
    difference: float = summary.get_week_work_required_difference()

    if difference >= 0:
        Logger.log_success(f"Difference : {float_to_hours_minutes(difference)}")
    else:
        Logger.log_error(f"Difference : {float_to_hours_minutes(difference)}")

    Logger.log_info("=============Month Hours=============")
    difference: float = summary.month_work_required_difference

    Logger.log_info(f"Total Month Hours: {float_to_hours_minutes(summary.total_month_hours)}")
    Logger.log_info(
        f"Total Month Hours / required hours : {float_to_hours_minutes(summary.total_month_hours)} / "
        f"{float_to_hours_minutes(summary.required_hours_for_month)}"
    )
    if difference >= 0:
        Logger.log_success(f"Difference : {float_to_hours_minutes(difference)}")
    else:
        Logger.log_error(f"Difference : {float_to_hours_minutes(difference)}")


def get_total_hours_summary(tempos) -> LogsSummary:

    logs_summary = LogsSummary()

    week_start_date = get_start_of_week()

    for tempo in tempos:
        Logger.log_debug(f"Getting hours for {tempo['name']}")
        logs_list: List[HoursLog] = get_hours(tempo)

        current_month_total = 0
        current_week_total = 0

        for log in logs_list:
            logs_summary.add_day_hours(log.date, log.hours)
            current_month_total += log.hours

            if log.date >= week_start_date:
                current_week_total += log.hours

        Logger.log_info(f"Total weekly hours for {tempo['name']}: {current_week_total}")
        Logger.log_info(f"Total monthly hours for {tempo['name']}: {current_month_total}")

    return logs_summary


def get_jira_projects() -> dict:
    config_file_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_file_path, "r") as config_file:
        config = json.load(config_file)
        return config["projects"]


def get_hours(tempo_details: dict) -> List[HoursLog]:
    today = datetime.datetime.today()
    Logger.log_debug(f"Today: {today}")

    first_day_month = today.replace(day=1)
    Logger.log_debug(f"First day of month: {first_day_month}")

    api_url = (
        f"{TEMPO_API_BASE}{TEMPO_API_WORKLOGS_ENDPOINT}/{tempo_details['user']}?"
        f"from={first_day_month.strftime('%Y-%m-%d')}&"
        f"to={today.strftime('%Y-%m-%d')}"
    )

    return get_hours_from_api(api_url, tempo_details["tempo_token"])


def get_hours_from_api(
    api_url: str, token: str, accumulative_hours: Union[None, List[HoursLog]] = None
) -> List[HoursLog]:

    if accumulative_hours is None:
        accumulative_hours = []

    Logger.log_debug(f"Getting hours from API: {api_url}")
    response = requests.get(api_url, headers={"Authorization": f"Bearer {token}"})

    if response.status_code != 200:
        print("Error getting hours from API")
        print("response.text: ", response.text)
        exit(1)

    response = response.json()

    for log in response.get("results", []):
        logged_time = log["timeSpentSeconds"] / 3600
        start_date = datetime.datetime.strptime(log["startDate"], "%Y-%m-%d").date()

        Logger.log_debug(f"Adding {logged_time} hours for {start_date} :: {log['issue']['self']}")
        accumulative_hours.append(HoursLog(start_date, logged_time))

    next_api_url = response.get("metadata", {}).get("next", "")

    if next_api_url:
        Logger.log_debug(f"Next API URL: {next_api_url}")
        return get_hours_from_api(next_api_url, token, accumulative_hours)
    else:
        return accumulative_hours


if __name__ == "__main__":
    cli_main()
else:
    launch_ui()
