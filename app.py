import json
import os
from dataclasses import dataclass
import datetime
import requests


DEBUG = bool(os.environ.get("DEBUG", False))

TEMPO_API_BASE = os.environ.get("TEMPO_API_BASE", "https://api.tempo.io/4")
TEMPO_API_WORKLOGS_ENDPOINT = os.environ.get("TEMPO_API_WORKLOGS_ENDPOINT", "/worklogs/user")


@dataclass
class LogsSummary:
    total_week_hours: float
    total_month_hours: float

    def _get_working_days_in_month(self):
        today = datetime.date.today()
        working_days = 0

        for day in range(1, today.day + 1):
            date = datetime.date(today.year, today.month, day)
            if date.weekday() < 5:  # Monday to Friday (0-4 are weekdays)
                working_days += 1

        return working_days

    @property
    def required_hours_for_week(self) -> float:
        today_week_day = min(datetime.datetime.today().weekday() + 1, 5)
        return today_week_day * 8

    @property
    def week_work_required_difference(self) -> float:
        return self.total_week_hours - self.required_hours_for_week

    @property
    def required_hours_for_month(self) -> float:
        working_days = self._get_working_days_in_month()
        return working_days * 8

    @property
    def month_work_required_difference(self) -> float:
        return self.total_month_hours - self.required_hours_for_month


class Logger:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'

    @staticmethod
    def log_info(message):
        print(Logger.BLUE + '[INFO] ' + message + Logger.RESET)

    @staticmethod
    def log_success(message):
        print(Logger.GREEN + '[SUCCESS] ' + message + Logger.RESET)

    @staticmethod
    def log_error(message):
        print(Logger.RED + '[ERROR] ' + message + Logger.RESET)

    @staticmethod
    def log_debug(message):
        if DEBUG:
            print(Logger.YELLOW + '[DEBUG] ' + message + Logger.RESET)

def float_to_hours_minutes(value: float):
    return f"{int(value)}h {int((abs(value) % 1) * 60)}m"

def launch_ui():
    tempos = get_jira_projects()
    pass


def cli_main():
    tempos = get_jira_projects()

    summary: LogsSummary = get_total_hours_summary(tempos)

    print("=============Week Hours=============")
    Logger.log_info(f"Total Week Hours: {float_to_hours_minutes(summary.total_week_hours)}")
    Logger.log_info(f"Total Week Hours / required hours : {float_to_hours_minutes(summary.total_week_hours)} / {float_to_hours_minutes(summary.required_hours_for_week)}")
    difference = summary.week_work_required_difference

    if difference >= 0:
        Logger.log_success(f"Difference : {float_to_hours_minutes(difference)}")
    else:
        Logger.log_error(f"Difference : {float_to_hours_minutes(difference)}")

    print("=============Month Hours=============")
    difference = summary.month_work_required_difference

    Logger.log_info(f"Total Month Hours: {float_to_hours_minutes(summary.total_month_hours)}")
    Logger.log_info(f"Total Month Hours / required hours : {float_to_hours_minutes(summary.total_month_hours)} / {float_to_hours_minutes(summary.required_hours_for_month)}")
    if difference >= 0:
        Logger.log_success(f"Difference : {float_to_hours_minutes(difference)}")
    else:
        Logger.log_error(f"Difference : {float_to_hours_minutes(difference)}")


def get_total_hours_summary(tempos):
    total_week_hours = 0
    total_month_hours = 0

    for tempo in tempos:
        Logger.log_debug(f"Getting hours for {tempo['name']}")
        week_hours, month_hours = get_hours(tempo)
        total_week_hours += week_hours
        total_month_hours += month_hours

    return LogsSummary(total_week_hours, total_month_hours)


def get_jira_projects():
    config_file_path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(config_file_path, "r") as config_file:
        config = json.load(config_file)
        return config["projects"]


def get_hours(tempo_details: dict):
    today = datetime.datetime.today()
    Logger.log_debug(f"Today: {today}")

    last_monday = today - datetime.timedelta(days=today.weekday())
    Logger.log_debug(f"Last Monday: {last_monday}")

    first_day_month = today.replace(day=1)
    Logger.log_debug(f"First day of month: {first_day_month}")

    api_url = (
        f"{TEMPO_API_BASE}{TEMPO_API_WORKLOGS_ENDPOINT}/{tempo_details['user']}?"
        f"from={last_monday.strftime('%Y-%m-%d')}&"
        f"to={today.strftime('%Y-%m-%d')}"
    )

    week_hours = get_hours_from_api(api_url, tempo_details["tempo_token"], 0)

    api_url = (
        f"{TEMPO_API_BASE}{TEMPO_API_WORKLOGS_ENDPOINT}/{tempo_details['user']}?"
        f"from={first_day_month.strftime('%Y-%m-%d')}&"
        f"to={today.strftime('%Y-%m-%d')}"
    )
    month_hours = get_hours_from_api(api_url, tempo_details["tempo_token"], 0)

    Logger.log_info(f"This week's hours for {tempo_details['name']}: {week_hours}")
    Logger.log_info(f"This month's hours for {tempo_details['name']}: {month_hours}")

    return week_hours, month_hours


def get_hours_from_api(api_url, token, accumulative_hours=0):
    Logger.log_debug(f"Getting hours from API: {api_url}")

    response = requests.get(api_url, headers={
        "Authorization": f"Bearer {token}"
    })

    if response.status_code != 200:
        print("Error getting hours from API")
        print("response.text: ", response.text)
        exit(1)

    response = response.json()
    week_hours = sum([worklog["timeSpentSeconds"] for worklog in response.get("results", [])]) / 3600
    accumulative_hours += week_hours

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
