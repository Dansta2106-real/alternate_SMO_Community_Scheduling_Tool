# scoring.py

from config import (
    DOUBLE_PREREC_PENALTY,
    PREREC_PENALTY,
    ISOLATED_RACE_PENALTY,
    CONSECUTIVE_BONUS,
    LATE_PREREC_PENALTY,
    EMPTY_DAY_PENALTY,
    PREFERRED_SLOT_PENALTY,
    CENTER_SLOT_PENALTY
)
from model import is_adjacent_slot_pair, slot_outer_distance



def calculate_score(
    solution,
    match_data,
    runner_preferred_slots,
    num_slots,
    slots_per_day
):
    """
    Calculate detailed human-readable penalty score.

    solution format:

    {
        "data": [
            {
                "race": int,
                "slot": int,
                "p1_prerec": bool,
                "p2_prerec": bool
            }
        ]
    }
    """


    # ------------------------------------------------
    # Prerecorded calculations
    # ------------------------------------------------

    double_prerec = 0

    prerec_count = 0


    for race in solution["data"]:

        if (
            race["p1_prerec"]
            and
            race["p2_prerec"]
        ):

            double_prerec += 1


        if race["p1_prerec"]:

            prerec_count += 1


        if race["p2_prerec"]:

            prerec_count += 1



    # ------------------------------------------------
    # Preferred slot penalties
    # ------------------------------------------------

    shared_preference_penalty = 0
    bad_r1_preference_penalty = 0
    bad_r2_preference_penalty = 0
    global_r1_preference_penalty = 0
    global_r2_preference_penalty = 0
    late_prerec_penalty = 0


    for race in solution["data"]:

        match = match_data[
            race["race"]
        ]

        slot = race["slot"]

        p1 = race["p1_prerec"]

        p2 = race["p2_prerec"]

        preferred1 = set(match["r1_preferred"])

        preferred2 = set(match["r2_preferred"])

        shared_preferred = preferred1 & preferred2

        if (
            not p1
            and
            not p2
            and
            slot not in shared_preferred
        ):
            shared_preference_penalty += 1

        if not p1 and slot not in preferred1:
            bad_r1_preference_penalty += 1

        if not p2 and slot not in preferred2:
            bad_r2_preference_penalty += 1

        global_r1_preference = runner_preferred_slots.get(
            match["runner1"],
            set()
        )

        global_r2_preference = runner_preferred_slots.get(
            match["runner2"],
            set()
        )

        if slot not in global_r1_preference:
            global_r1_preference_penalty += 1

        if slot not in global_r2_preference:
            global_r2_preference_penalty += 1

        if p1:
            late_prerec_penalty += (
                LATE_PREREC_PENALTY
                *
                (
                    num_slots
                    -
                    slot
                    -
                    1
                )
            )

        if p2:
            late_prerec_penalty += (
                LATE_PREREC_PENALTY
                *
                (
                    num_slots
                    -
                    slot
                    -
                    1
                )
            )


    preferred_penalty = (
        shared_preference_penalty
        +
        bad_r1_preference_penalty
        +
        bad_r2_preference_penalty
        +
        global_r1_preference_penalty
        +
        global_r2_preference_penalty
    )


    # ------------------------------------------------
    # Occupied slots
    # ------------------------------------------------

    occupied = sorted(
        {
            race["slot"]
            for race in solution["data"]
        }
    )



    occupied_set = set(
        occupied
    )



    # ------------------------------------------------
    # Consecutive bonuses
    #
    # IMPORTANT:
    #
    # A B C
    #
    # becomes:
    #
    # A-B bonus
    #
    # not:
    #
    # A-B
    # B-C
    #
    # ------------------------------------------------

    bonus_count = 0

    used_for_bonus = set()
    slot_values = list(range(num_slots))


    for slot in occupied:

        if slot in used_for_bonus:

            continue


        right_neighbour = slot + 1

        if (
            right_neighbour in occupied_set
            and
            right_neighbour not in used_for_bonus
            and
            is_adjacent_slot_pair(
                slot,
                right_neighbour,
                slot_values,
                slots_per_day
            )
        ):

            bonus_count += 1

            used_for_bonus.add(
                slot
            )

            used_for_bonus.add(
                right_neighbour
            )



    # ------------------------------------------------
    # Isolated races
    # ------------------------------------------------

    isolated_count = 0



    for slot in occupied:

        has_left = (
            slot > 0
            and
            slot - 1 in occupied_set
            and
            is_adjacent_slot_pair(
                slot - 1,
                slot,
                slot_values,
                slots_per_day
            )
        )

        has_right = (
            slot < num_slots - 1
            and
            slot + 1 in occupied_set
            and
            is_adjacent_slot_pair(
                slot,
                slot + 1,
                slot_values,
                slots_per_day
            )
        )

        if (
            not has_left
            and
            not has_right
        ):

            isolated_count += 1



    # ------------------------------------------------
    # Empty days
    # ------------------------------------------------

    empty_days = 0



    for day in range(num_slots // slots_per_day):

        start = (
            day *
            slots_per_day
        )


        end = (
            start +
            slots_per_day
        )


        races_today = any(
            start <= x < end
            for x in occupied
        )


        if not races_today:

            empty_days += 1

    # ------------------------------------------------
    # Center-slot preference
    # ------------------------------------------------

    center_slot_penalty = 0

    for slot in occupied:
        center_slot_penalty += (
            slot_outer_distance(
                slot,
                slots_per_day
            )
            *
            CENTER_SLOT_PENALTY
        )



    # ------------------------------------------------
    # Final score
    # ------------------------------------------------

    score = (

        double_prerec *
        DOUBLE_PREREC_PENALTY

        +

        prerec_count *
        PREREC_PENALTY

        +

        bonus_count *
        CONSECUTIVE_BONUS

        +

        isolated_count *
        ISOLATED_RACE_PENALTY

        +

        empty_days *
        EMPTY_DAY_PENALTY

        +

        preferred_penalty *
        PREFERRED_SLOT_PENALTY

        +

        center_slot_penalty

        +

        late_prerec_penalty
    )



    return {

        "double_prerec": double_prerec,

        "prerec_count": prerec_count,

        "bonus_count": bonus_count,

        "isolated_count": isolated_count,

        "empty_days": empty_days,

        "preferred_penalty": preferred_penalty,

        "center_slot_penalty": center_slot_penalty,

        "late_prerec_penalty": late_prerec_penalty,

        "score": score
    }



def print_score(score):

    print()

    print(
        "Penalty breakdown:"
    )


    print(
        f"Double prerecorded matches: "
        f"{score['double_prerec']} x "
        f"{DOUBLE_PREREC_PENALTY:,} = "
        f"{score['double_prerec'] * DOUBLE_PREREC_PENALTY:,}"
    )


    print(
        f"Prerecorded runners: "
        f"{score['prerec_count']} x "
        f"{PREREC_PENALTY:,} = "
        f"{score['prerec_count'] * PREREC_PENALTY:,}"
    )


    print(
        f"Consecutive race bonuses: "
        f"{score['bonus_count']} x "
        f"{CONSECUTIVE_BONUS} = "
        f"{score['bonus_count'] * CONSECUTIVE_BONUS}"
    )


    print(
        f"Isolated races: "
        f"{score['isolated_count']} x "
        f"{ISOLATED_RACE_PENALTY} = "
        f"{score['isolated_count'] * ISOLATED_RACE_PENALTY}"
    )


    print(
        f"Empty days: "
        f"{score['empty_days']} x "
        f"{EMPTY_DAY_PENALTY} = "
        f"{score['empty_days'] * EMPTY_DAY_PENALTY}"
    )


    print(
        f"Preferred slot penalties: "
        f"{score['preferred_penalty']} x "
        f"{PREFERRED_SLOT_PENALTY} = "
        f"{score['preferred_penalty'] * PREFERRED_SLOT_PENALTY}"
    )


    print(
        f"Outer-slot penalties: "
        f"{score['center_slot_penalty']}"
    )


    print(
        f"Late prerecorded penalties: "
        f"{score['late_prerec_penalty']}"
    )


    print(
        f"Total penalty score: "
        f"{score['score']}"
    )