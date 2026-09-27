import calendar
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from croniter import croniter
from cron_descriptor import ExpressionDescriptor, Options


# Timezone to assume when a cron has no "TZ=" prefix
DEFAULT_TIMEZONE = "Asia/Kolkata"

MINUTES_PER_DAY = 24 * 60


def convert_schedules(schedules):
    """
    Convert a list of schedules to UTC.
    """
    results = []

    for schedule in schedules:
        try:
            if "cron" not in schedule:
                raise ValueError("Missing 'cron' field in the schedule")
            utc_cron, summary = convert_to_utc(schedule["cron"])
            results.append({"cron": utc_cron, "scheduleSummary": summary})
        except Exception as error:
            failed_item = dict(schedule)
            failed_item["scheduleSummary"] = str(error)
            results.append(failed_item)

    return results


def convert_to_utc(cron_text):
    """Convert one cron string to UTC. Returns (utc_cron, summary)."""
    timezone_name, fields = split_timezone_and_fields(cron_text)
    minute, hour, day_of_month, month, day_of_week = fields

    if not minute.isdigit() or not hour.isdigit():
        raise ValueError("Minute and hour must be fixed numbers (for example '6 19')")

    offset_minutes = get_utc_offset_in_minutes(timezone_name)

    local_minutes = int(hour) * 60 + int(minute)
    utc_minutes = local_minutes - offset_minutes

    day_shift = 0
    if utc_minutes < 0:
        utc_minutes += MINUTES_PER_DAY
        day_shift = -1
    elif utc_minutes >= MINUTES_PER_DAY:
        utc_minutes -= MINUTES_PER_DAY
        day_shift = 1

    utc_hour = utc_minutes // 60
    utc_minute = utc_minutes % 60

    if day_shift != 0:
        day_of_week = shift_day_of_week(fields, day_shift)
        day_of_month, month = shift_day_of_month(fields, day_shift, timezone_name)

    utc_cron = f"{utc_minute} {utc_hour} {day_of_month} {month} {day_of_week}"

    local_cron = " ".join(fields)

    summary = build_summary(utc_cron, utc_hour, utc_minute)
    return utc_cron, summary


def split_timezone_and_fields(cron_text):
    """
    Separate the optional "TZ=..." prefix from the five cron fields.

    "TZ=Asia/Calcutta 6 19 * * *"  ->  ("Asia/Calcutta", ["6", "19", "*", "*", "*"])
    """
    parts = cron_text.split()
    timezone_name = DEFAULT_TIMEZONE

    if parts and (parts[0].startswith("TZ=") or parts[0].startswith("CRON_TZ=")):
        prefix = parts.pop(0)
        timezone_name = prefix.split("=", 1)[1].strip("\"'")

    if len(parts) != 5:
        raise ValueError(f"Expected 5 cron fields, got {len(parts)}")

    return timezone_name, parts


def get_utc_offset_in_minutes(timezone_name):
    """
    Return how far the timezone is ahead of UTC, in minutes (IST = 330).

    Timezones with daylight saving time are rejected, because their
    offset changes during the year and a single UTC cron can't follow that.
    """
    zone = ZoneInfo(timezone_name)

    year = datetime.now(timezone.utc).year

    winter_offset = datetime(year, 1, 1, tzinfo=zone).utcoffset()
    summer_offset = datetime(year, 7, 1, tzinfo=zone).utcoffset()

    if winter_offset != summer_offset:
        raise ValueError(
            f"{timezone_name} uses daylight saving time, so its UTC offset "
            "changes during the year and one fixed UTC cron can't follow it"
        )

    return int(winter_offset.total_seconds() // 60)


def shift_day_of_week(fields, day_shift):
    """
    Move the day-of-week field by one day.
    """
    day_of_week = fields[4]
    if day_of_week == "*":
        return day_of_week

    expanded_fields = croniter.expand(" ".join(fields))[0]
    local_days = expanded_fields[4]

    utc_days = set()
    for day in local_days:
        utc_days.add((int(day) + day_shift) % 7)

    return ",".join(str(day) for day in sorted(utc_days))


def ordinal(number):
    if 11 <= number % 100 <= 13:
        return f"{number}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def join_with_or(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def shift_day_of_month(fields, day_shift, timezone_name):
    """
    Move the day-of-month field by one day. Returns (day_of_month, month).
    """
    minute, hour, day_of_month, month = fields[0], fields[1], fields[2], fields[3]

    zone = ZoneInfo(timezone_name)
    zone_label = datetime(2026, 1, 1, tzinfo=zone).tzname() or timezone_name
    local_time_text = f"{int(hour):02d}:{int(minute):02d} {zone_label}"
    month_direction = "previous" if day_shift < 0 else "next"

    if day_of_month == "*":
        if month != "*":
            raise ValueError(
                f"This schedule runs every day of specific months at {local_time_text}, "
                f"but in UTC the edge run moves into the {month_direction} month, "
                "so it can't be converted exactly"
            )
        return day_of_month, month

    if not day_of_month.isdigit():
        raise ValueError(
            f"Can't shift a complex day-of-month value '{day_of_month}' to the "
            f"{month_direction} day in UTC"
        )

    local_day = int(day_of_month)

    if month == "*":
        months = range(1, 13)
    else:
        months = croniter.expand(" ".join(fields))[0][3]

    normal_year_dates = set()
    leap_year_dates = set()
    leap_example = None 

    for month_number in months:
        month_number = int(month_number)

        exists_in_leap_year = local_day <= calendar.monthrange(2024, month_number)[1]
        exists_in_normal_year = local_day <= calendar.monthrange(2025, month_number)[1]

        if not exists_in_leap_year and not exists_in_normal_year:
            continue  # e.g. 31 April: the job never runs in this month

        if exists_in_leap_year != exists_in_normal_year:
            shifted = date(2024, month_number, local_day) + timedelta(days=day_shift)
            raise ValueError(
                f"{local_day} {calendar.month_name[month_number]} only exists in leap years, "
                f"and in UTC this run moves to {shifted.day} {calendar.month_name[shifted.month]}, "
                "so it can't be converted exactly"
            )

        leap_year_result = date(2024, month_number, local_day) + timedelta(days=day_shift)
        normal_year_result = date(2025, month_number, local_day) + timedelta(days=day_shift)

        normal_year_dates.add((normal_year_result.day, normal_year_result.month))
        leap_year_dates.add((leap_year_result.day, leap_year_result.month))

        if leap_example is None and (leap_year_result.month, leap_year_result.day) != (
            normal_year_result.month, normal_year_result.day
        ):
            leap_example = (month_number, normal_year_result, leap_year_result)

    all_utc_days = sorted({day for day, _ in normal_year_dates | leap_year_dates})

    # Case 1: the UTC day of the month is not the same for every run.
    if len(all_utc_days) > 1:
        day_list = join_with_or([ordinal(day) for day in all_utc_days])
        if local_day == 1 and day_shift < 0:
            raise ValueError(
                f"{local_time_text} on the 1st is the last day of the previous month "
                f"in UTC ({day_list}), which one cron line can't express"
            )
        raise ValueError(
            f"{local_time_text} on the {ordinal(local_day)} lands on the {day_list} "
            f"of the {month_direction} month in UTC, which one cron line can't express"
        )

    # Case 2: same day every month, but it changes in leap years
    if leap_example is not None:
        month_number, normal_result, leap_result = leap_example
        raise ValueError(
            f"{local_time_text} on {local_day} {calendar.month_name[month_number]} is "
            f"{normal_result.day} {calendar.month_name[normal_result.month]} in UTC, "
            f"but {leap_result.day} {calendar.month_name[leap_result.month]} in leap years, "
            "so it can't be converted exactly"
        )

    utc_months = sorted({month_number for _, month_number in normal_year_dates})
    if len(utc_months) == 12:
        month_field = "*"
    else:
        month_field = ",".join(str(month_number) for month_number in utc_months)

    return str(all_utc_days[0]), month_field

def build_summary(utc_cron, utc_hour, utc_minute):
    """Create a readable description, e.g. 'Daily at 13:36 UTC'."""
    time_text = f"{utc_hour:02d}:{utc_minute:02d}"

    runs_every_day = utc_cron.endswith("* * *")
    if runs_every_day:
        return f"Daily at {time_text} UTC"

    options = Options()
    options.use_24hour_time_format = True
    description = str(ExpressionDescriptor(utc_cron, options))

    return description.replace(time_text, f"{time_text} UTC", 1)
