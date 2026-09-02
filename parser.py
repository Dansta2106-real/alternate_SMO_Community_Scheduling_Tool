# parser.py

import pandas as pd
import re

from config import DAYS, HOURS_PER_DAY


# ----------------------------------------------------
# Constants
# ----------------------------------------------------

UTC_SLOTS = [f"{hour:02d}:00 UTC" for hour in range(HOURS_PER_DAY)]


# ----------------------------------------------------
# Time helpers
# ----------------------------------------------------

def timezone_offset(tz):

    tz = str(tz).strip()


    if tz == "UTC":
        return 0


    match = re.match(
        r"UTC([+-]\d+)",
        tz
    )


    if not match:

        raise Exception(
            f"Invalid timezone: {tz}"
        )


    return int(
        match.group(1)
    )



def parse_time(day_index, value):

    value = str(value).strip().upper()
    value = re.sub(r"\s+UTC$", "", value)
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value)

    if not match:
        raise ValueError(f"Unsupported slot: {value}")

    hour = int(match.group(1))
    minute = int(match.group(2))

    if minute >= 60 or hour > HOURS_PER_DAY:
        raise ValueError(f"Unsupported slot: {value}")

    if hour == HOURS_PER_DAY and minute != 0:
        raise ValueError(f"Unsupported slot: {value}")

    # Legacy half-hour entries cannot be starts in the new schedule.
    # Round them up to the next hourly start.
    if minute:
        hour += 1

    return (
        day_index * HOURS_PER_DAY
        +
        hour
    )



def to_utc(slot_value, offset):

    return (
        slot_value
        -
        offset
    )



def slot_to_minutes(day_index, slot):

    return (
        day_index * HOURS_PER_DAY
        +
        slot
    )



def display_time(slot_value):

    if slot_value is None:
        return ""


    day = slot_value // HOURS_PER_DAY

    slot_index = slot_value % HOURS_PER_DAY


    if day < 0:
        day = 0

    if day >= len(DAYS):
        day = len(DAYS) - 1

    if slot_index < 0:
        slot_index = 0

    if slot_index >= len(UTC_SLOTS):
        slot_index = len(UTC_SLOTS) - 1


    return (
        f"{DAYS[day].capitalize()} "
        f"{slot_index:02d}:00 UTC"
    )



# ----------------------------------------------------
# Load availability CSV
# ----------------------------------------------------

def load_availability(
    filename
):

    avail = pd.read_csv(
        filename
    )


    # Normalize headers

    avail.columns = (
        avail.columns
        .str.strip()
        .str.lower()
    )


    # Clean runner names

    avail["runner"] = (
        avail["runner"]
        .astype(str)
        .str.replace(
            '"',
            '',
            regex=False
        )
        .str.replace(
            "\xa0",
            " ",
            regex=False
        )
        .str.strip()
    )


    availability = {}



    for _, row in avail.iterrows():

        runner = row["runner"]


        offset = timezone_offset(row.get("timezone", "UTC"))


        utc_times = set()



        for day_index, day in enumerate(DAYS):


            values = row.get(
                day,
                ""
            )


            if pd.isna(values):

                continue



            values = str(values).strip()


            if values == "" or values.upper() == "NOTHING":

                continue



            for t in values.split(","):

                t = t.strip()


                local_slot = parse_time(
                    day_index,
                    t
                )


                utc_slot = to_utc(
                    local_slot,
                    offset
                )


                if 0 <= utc_slot < len(DAYS) * HOURS_PER_DAY:
                    utc_times.add(utc_slot)



        availability[runner] = utc_times



    return availability



# ----------------------------------------------------
# Load matchups CSV
# ----------------------------------------------------

def load_matchups(
    filename
):

    matches = pd.read_csv(
        filename
    )


    matches.columns = (
        matches.columns
        .str.strip()
        .str.lower()
    )


    matches["runner1"] = (
        matches["runner1"]
        .astype(str)
        .str.replace(
            '"',
            '',
            regex=False
        )
        .str.strip()
    )


    matches["runner2"] = (
        matches["runner2"]
        .astype(str)
        .str.replace(
            '"',
            '',
            regex=False
        )
        .str.strip()
    )


    return matches



# ----------------------------------------------------
# Create UTC slot lookup
# ----------------------------------------------------

def create_slot_lookup():

    slot_lookup = {}

    all_slots = []


    for day_index in range(len(DAYS)):

        for slot in range(HOURS_PER_DAY):


            slot_value = slot_to_minutes(
                day_index,
                slot
            )


            slot_lookup[slot_value] = len(
                all_slots
            )


            all_slots.append(
                slot_value
            )



    return (
        slot_lookup,
        all_slots
    )

def calculate_preferred_slots(
    availability
):

    preferred = {}


    for runner, slots in availability.items():

        runner_preferences = set()


        sorted_slots = sorted(
            slots
        )


        # Split into consecutive groups

        groups = []

        current = []


        for slot in sorted_slots:

            if not current:

                current.append(slot)

            else:

                if slot - current[-1] == 90:

                    current.append(slot)

                else:

                    groups.append(
                        current
                    )

                    current = [
                        slot
                    ]


        if current:

            groups.append(
                current
            )



        for group in groups:

            length = len(group)


            # Only odd sized groups have
            # a true middle

            if length % 2 == 1:

                middle = group[
                    length // 2
                ]

                runner_preferences.add(
                    middle
                )


        preferred[runner] = runner_preferences


    return preferred