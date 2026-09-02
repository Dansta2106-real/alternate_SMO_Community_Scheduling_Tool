# output.py

import pandas as pd

from scoring import (
    calculate_score,
    print_score
)



def format_runner(
    name,
    prerecorded
):

    if prerecorded:

        return (
            f"{name} (Prerecorded)"
        )

    return name


def build_prerec_warning_messages(
    race,
    match,
    scheduled_label
):

    warnings = []


    if (
        race["p1_prerec"]
        and
        match["r1_slots"]
        and
        race["slot"] <= min(match["r1_slots"])
    ):

        warnings.append(
            "Prerecord before first available slot"
        )


    if (
        race["p2_prerec"]
        and
        match["r2_slots"]
        and
        race["slot"] <= min(match["r2_slots"])
    ):

        warnings.append(
            "Prerecord before first available slot"
        )

    for runner in match.get("missing_availability_runners", []):
        warnings.append(
            f"{runner} has not submitted availabilities"
        )


    return warnings



def build_dataframe(
    solution,
    match_data,
    all_slots,
    display_time
):

    rows = []


    for race in solution["data"]:

        match = match_data[
            race["race"]
        ]


        runner1 = format_runner(
            match["runner1"],
            race["p1_prerec"]
        )


        runner2 = format_runner(
            match["runner2"],
            race["p2_prerec"]
        )

        scheduled_label = display_time(
            all_slots[
                race["slot"]
            ]
        )

        warnings = build_prerec_warning_messages(
            race,
            match,
            scheduled_label
        )


        rows.append(
            {
                "runner1":
                    runner1,

                "runner2":
                    runner2,

                "slot":
                    race["slot"],

                "scheduled":
                    scheduled_label,

                "warning":
                    " | ".join(warnings) if warnings else "Nothing",
            }
        )



    df = pd.DataFrame(
        rows
    )


    df = df.sort_values(
        by="slot"
    )


    return df[
        [
            "runner1",
            "runner2",
            "scheduled",
            "warning"
        ]
    ]


def find_prerec_first_slot_violations(
    solution,
    match_data,
    all_slots,
    display_time
):

    violations = []


    for race in solution["data"]:

        match_index = race["race"]

        match = match_data[
            match_index
        ]

        scheduled_label = display_time(
            all_slots[
                race["slot"]
            ]
        )

        warnings = build_prerec_warning_messages(
            race,
            match,
            scheduled_label
        )

        violations.extend(warnings)


    return violations


def print_prerec_first_slot_violations(
    violations
):

    if not violations:
        return


    print()

    print(
        "!" * 10,
        "FIRST-SLOT PRERECORD VIOLATION",
        "!" * 10
    )


    for violation in violations:

        print(
            violation
        )

    print(
        "!" * 46
    )



def display_solutions(
    solutions,
    match_data,
    all_slots,
    display_time,
    slots_per_day,
    output_file,
    runner_preferred_slots
):


    best_schedule = None



    for index, solution in enumerate(
        solutions[:3],
        start=1
    ):


        print()

        print(
            "=" * 15,
            f"Solution #{index}",
            "=" * 15
        )



        df = build_dataframe(
            solution,
            match_data,
            all_slots,
            display_time
        )


        print(
            df.to_string(
                index=False
            )
        )


        violations = find_prerec_first_slot_violations(
            solution,
            match_data,
            all_slots,
            display_time
        )


        print_prerec_first_slot_violations(
            violations
        )



        score = calculate_score(
            solution,
            match_data,
            runner_preferred_slots,
            len(all_slots),
            slots_per_day
        )


        print_score(
            score
        )



        if index == 1:

            best_schedule = df



    best_schedule.to_csv(
        output_file,
        index=False
    )


    print()

    print(
        f"Saved schedule to {output_file}"
    )


    return best_schedule