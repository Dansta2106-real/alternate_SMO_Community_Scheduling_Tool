# model.py

from ortools.sat.python import cp_model

from config import (
    DOUBLE_PREREC_PENALTY,
    PREREC_PENALTY,
    ISOLATED_RACE_PENALTY,
    CONSECUTIVE_BONUS,
    LATE_PREREC_PENALTY,
    NO_AVAILABILITY_LATE_PENALTY,
    EMPTY_DAY_PENALTY,
    PREFERRED_SLOT_PENALTY,
    CENTER_SLOT_PENALTY
)
from config import START_GAP_HOURS


def is_adjacent_slot_pair(left_index, right_index, slot_values, slots_per_day):
    if left_index < 0 or right_index < 0:
        return False

    if left_index >= len(slot_values) or right_index >= len(slot_values):
        return False

    same_day = (
        slot_values[left_index] // slots_per_day
        ==
        slot_values[right_index] // slots_per_day
    )

    return (
        same_day
        and
        slot_values[right_index] % slots_per_day
        ==
        slot_values[left_index] % slots_per_day + 1
    )


def slot_outer_distance(slot_value, slots_per_day):
    """Return distance from the daily center (0 for center-most slots)."""

    slot_in_day = slot_value % slots_per_day
    nearest_edge = min(slot_in_day, slots_per_day - 1 - slot_in_day)
    max_nearest_edge = (slots_per_day - 1) // 2

    return max_nearest_edge - nearest_edge


def build_model(
    match_data,
    num_slots,
    slots_per_day,
    preferred_slots,
    slot_values
):

    model = cp_model.CpModel()


    # ------------------------------------------------
    # Race slot variables
    # ------------------------------------------------

    race_slot = []

    prerec_flags = []


    for i, match in enumerate(match_data):

        slot = model.NewIntVarFromDomain(
            cp_model.Domain.FromValues(
                match["possible_slots"]
            ),
            f"race_{i}_slot"
        )


        race_slot.append(
            slot
        )


        p1 = model.NewBoolVar(
            f"race_{i}_runner1_prerec"
        )


        p2 = model.NewBoolVar(
            f"race_{i}_runner2_prerec"
        )


        prerec_flags.append(
            p1
        )

        prerec_flags.append(
            p2
        )



        # Runner 1 availability

        model.AddAllowedAssignments(
            [
                slot,
                p1
            ],

            [
                (s, 0)
                for s in match["r1_slots"]
            ]
            +
            [
                (s, 1)
                for s in match["possible_slots"]
                if s not in match["r1_slots"]
            ]
        )



        # Runner 2 availability

        model.AddAllowedAssignments(
            [
                slot,
                p2
            ],

            [
                (s, 0)
                for s in match["r2_slots"]
            ]
            +
            [
                (s, 1)
                for s in match["possible_slots"]
                if s not in match["r2_slots"]
            ]
        )



    # ------------------------------------------------
    # Race/slot matrix
    # ------------------------------------------------

    race_in_slot = []


    for r, slot_var in enumerate(race_slot):

        row = []


        for s in range(num_slots):

            b = model.NewBoolVar(
                f"race_{r}_uses_slot_{s}"
            )


            model.Add(
                slot_var == s
            ).OnlyEnforceIf(
                b
            )


            model.Add(
                slot_var != s
            ).OnlyEnforceIf(
                b.Not()
            )


            row.append(
                b
            )


        race_in_slot.append(
            row
        )

    # ------------------------------------------------
    # Match duration and required break
    # ------------------------------------------------

    for left in range(len(match_data)):
        for right in range(left + 1, len(match_data)):
            start_distance = model.NewIntVar(
                0,
                num_slots,
                f"start_distance_{left}_{right}"
            )

            model.AddAbsEquality(
                start_distance,
                race_slot[left] - race_slot[right]
            )

            model.Add(start_distance >= START_GAP_HOURS)

    # ------------------------------------------------
    # Used start positions
    # ------------------------------------------------

    slot_used = []


    for s in range(num_slots):

        column = [
            race_in_slot[r][s]
            for r in range(len(match_data))
        ]


        model.Add(sum(column) <= 1)


        used = model.NewBoolVar(
            f"slot_{s}_used"
        )


        model.AddMaxEquality(
            used,
            column
        )


        slot_used.append(
            used
        )
    objective = []



    # ------------------------------------------------
    # Double prerecorded penalty
    # ------------------------------------------------

    for i in range(len(match_data)):

        p1 = prerec_flags[i * 2]

        p2 = prerec_flags[i * 2 + 1]


        both = model.NewBoolVar(
            f"double_prerec_{i}"
        )


        model.AddBoolAnd(
            [
                p1,
                p2
            ]
        ).OnlyEnforceIf(
            both
        )


        model.AddBoolOr(
            [
                p1.Not(),
                p2.Not()
            ]
        ).OnlyEnforceIf(
            both.Not()
        )


        objective.append(
            DOUBLE_PREREC_PENALTY * both
        )



    # ------------------------------------------------
    # Individual prerecorded penalty
    # ------------------------------------------------

    for p in prerec_flags:

        objective.append(
            PREREC_PENALTY * p
        )


    for i, match in enumerate(match_data):

        p1 = prerec_flags[i * 2]
        p2 = prerec_flags[i * 2 + 1]


        for s in match["possible_slots"]:

            at_slot = race_in_slot[i][s]

            late_penalty = model.NewBoolVar(
                f"late_penalty_{i}_{s}"
            )

            model.AddBoolAnd(
                [
                    at_slot,
                    p1
                ]
            ).OnlyEnforceIf(
                late_penalty
            )

            model.AddBoolOr(
                [
                    at_slot.Not(),
                    p1.Not()
                ]
            ).OnlyEnforceIf(
                late_penalty.Not()
            )

            objective.append(
                LATE_PREREC_PENALTY * (num_slots - s) * late_penalty
            )

        # Fully unavailable matchups are always prerecorded.
        # Place them as late as possible, but with a lower weight
        # than adding new prerecorded runners.
        if not match["r1_slots"] and not match["r2_slots"]:

            for s in match["possible_slots"]:

                at_slot = race_in_slot[i][s]

                objective.append(
                    NO_AVAILABILITY_LATE_PENALTY * (num_slots - s) * at_slot
                )


            late_penalty = model.NewBoolVar(
                f"late_penalty_{i}_{s}_p2"
            )

            model.AddBoolAnd(
                [at_slot, p2]
            ).OnlyEnforceIf(late_penalty)

            model.AddBoolOr(
                [at_slot.Not(), p2.Not()]
            ).OnlyEnforceIf(late_penalty.Not())

            objective.append(
                LATE_PREREC_PENALTY * (num_slots - s) * late_penalty
            )


    # ------------------------------------------------
    # Consecutive race bonuses
    #
    # A B C D
    #
    # counts:
    #
    # A-B bonus
    # C-D bonus
    #
    # NOT:
    #
    # A-B
    # B-C
    # C-D
    #
    # because a slot can only be used once
    # ------------------------------------------------

    consecutive_bonus = []


    for s in range(num_slots - 1):

        if not is_adjacent_slot_pair(
            s,
            s + 1,
            slot_values,
            slots_per_day
        ):

            continue


        pair = model.NewBoolVar(
            f"bonus_{s}_{s+1}"
        )


        model.AddBoolAnd(
            [
                slot_used[s],
                slot_used[s + 1]
            ]
        ).OnlyEnforceIf(
            pair
        )


        model.AddBoolOr(
            [
                slot_used[s].Not(),
                slot_used[s + 1].Not()
            ]
        ).OnlyEnforceIf(
            pair.Not()
        )


        consecutive_bonus.append(
            pair
        )


        objective.append(
            CONSECUTIVE_BONUS * pair
        )


    for i in range(1, len(consecutive_bonus)):

        model.Add(
            consecutive_bonus[i - 1] + consecutive_bonus[i] <= 1
        )



    # ------------------------------------------------
    # Isolated race penalty
    #
    # Race with no neighbour
    # ------------------------------------------------

    for s in range(num_slots):

        conditions = [
            slot_used[s]
        ]

        left_isolated = False
        right_isolated = False

        if s > 0:

            has_left = is_adjacent_slot_pair(
                s - 1,
                s,
                slot_values,
                slots_per_day
            )

            if has_left:
                conditions.append(
                    slot_used[s - 1].Not()
                )


        if s < num_slots - 1:

            has_right = is_adjacent_slot_pair(
                s,
                s + 1,
                slot_values,
                slots_per_day
            )

            if has_right:
                conditions.append(
                    slot_used[s + 1].Not()
                )


        isolated = model.NewBoolVar(
            f"isolated_{s}"
        )


        model.AddBoolAnd(
            conditions
        ).OnlyEnforceIf(
            isolated
        )


        opposite = [
            slot_used[s].Not()
        ]


        if s > 0:

            has_left = is_adjacent_slot_pair(
                s - 1,
                s,
                slot_values,
                slots_per_day
            )

            if has_left:
                opposite.append(
                    slot_used[s - 1]
                )


        if s < num_slots - 1:

            has_right = is_adjacent_slot_pair(
                s,
                s + 1,
                slot_values,
                slots_per_day
            )

            if has_right:
                opposite.append(
                    slot_used[s + 1]
                )


        model.AddBoolOr(
            opposite
        ).OnlyEnforceIf(
            isolated.Not()
        )


        objective.append(
            ISOLATED_RACE_PENALTY * isolated
        )

    # ------------------------------------------------
    # Empty day penalty
    # ------------------------------------------------

    for day in range(num_slots // slots_per_day):

        start = day * slots_per_day

        end = start + slots_per_day


        day_slots = slot_used[start:end]


        has_race = model.NewBoolVar(
            f"day_{day}_has_race"
        )


        model.AddMaxEquality(
            has_race,
            day_slots
        )


        empty = model.NewBoolVar(
            f"day_{day}_empty"
        )


        model.Add(
            has_race == 0
        ).OnlyEnforceIf(
            empty
        )


        model.Add(
            has_race == 1
        ).OnlyEnforceIf(
            empty.Not()
        )


        objective.append(
            EMPTY_DAY_PENALTY * empty
        )

    # ------------------------------------------------
    # Prefer center slots over outer slots
    # ------------------------------------------------

    for s in range(num_slots):

        outer_distance = slot_outer_distance(
            s,
            slots_per_day
        )

        if outer_distance == 0:
            continue

        objective.append(
            CENTER_SLOT_PENALTY
            *
            outer_distance
            *
            slot_used[s]
        )

    # ------------------------------------------------
    # Prefer middle of availability windows
    # ------------------------------------------------

    for r, match in enumerate(match_data):

        preferred = (
            set(match["r1_preferred"])
            &
            set(match["r2_preferred"])
        )

        for s in match["possible_slots"]:

            # Don't penalize preferred slots
            if s in preferred:
                continue

            at_slot = race_in_slot[r][s]

            p1 = prerec_flags[r * 2]
            p2 = prerec_flags[r * 2 + 1]

            penalty = model.NewBoolVar(
                f"preferred_penalty_{r}_{s}"
            )

            model.AddBoolAnd(
                [
                    at_slot,
                    p1.Not(),
                    p2.Not()
                ]
            ).OnlyEnforceIf(
                penalty
            )

            model.AddBoolOr(
                [
                    at_slot.Not(),
                    p1,
                    p2
                ]
            ).OnlyEnforceIf(
                penalty.Not()
            )

            objective.append(
                PREFERRED_SLOT_PENALTY * penalty
            )

    # ------------------------------------------------
    # Preferred availability slots
    # ------------------------------------------------


    for r, match in enumerate(match_data):

        for s in match["possible_slots"]:

            at_slot = race_in_slot[r][s]


            if s not in match["r1_preferred"]:

                bad_r1 = model.NewBoolVar(
                    f"bad_r1_preferred_{r}_{s}"
                )


                model.AddBoolAnd(
                    [
                        at_slot,
                        prerec_flags[r*2].Not()
                    ]
                ).OnlyEnforceIf(
                    bad_r1
                )


                model.AddBoolOr(
                    [
                        at_slot.Not(),
                        prerec_flags[r*2]
                    ]
                ).OnlyEnforceIf(
                    bad_r1.Not()
                )


                objective.append(
                    PREFERRED_SLOT_PENALTY * bad_r1
                )


            if s not in match["r2_preferred"]:

                bad_r2 = model.NewBoolVar(
                    f"bad_r2_preferred_{r}_{s}"
                )


                model.AddBoolAnd(
                    [
                        at_slot,
                        prerec_flags[r*2+1].Not()
                    ]
                ).OnlyEnforceIf(
                    bad_r2
                )


                model.AddBoolOr(
                    [
                        at_slot.Not(),
                        prerec_flags[r*2+1]
                    ]
                ).OnlyEnforceIf(
                    bad_r2.Not()
                )


                objective.append(
                    PREFERRED_SLOT_PENALTY * bad_r2
                )

    # ------------------------------------------------
    # Late prerecorded tie breaker
    #
    # If two schedules have the same
    # actual score:
    #
    # prefer prerecorded races later
    # ------------------------------------------------

    for r, match in enumerate(match_data):

        for s in match["possible_slots"]:

            lateness = num_slots - s


            at_slot = race_in_slot[r][s]


            p1 = prerec_flags[r * 2]

            p2 = prerec_flags[r * 2 + 1]



            late1 = model.NewBoolVar(
                f"late_p1_{r}_{s}"
            )


            model.AddBoolAnd(
                [
                    at_slot,
                    p1
                ]
            ).OnlyEnforceIf(
                late1
            )


            model.AddBoolOr(
                [
                    at_slot.Not(),
                    p1.Not()
                ]
            ).OnlyEnforceIf(
                late1.Not()
            )


            objective.append(
                lateness * late1
            )



            late2 = model.NewBoolVar(
                f"late_p2_{r}_{s}"
            )


            model.AddBoolAnd(
                [
                    at_slot,
                    p2
                ]
            ).OnlyEnforceIf(
                late2
            )


            model.AddBoolOr(
                [
                    at_slot.Not(),
                    p2.Not()
                ]
            ).OnlyEnforceIf(
                late2.Not()
            )


            objective.append(
                lateness * late2
            )



    # ------------------------------------------------
    # Preferred middle availability slots
    #
    # Very low priority.
    #
    # preferred_slots contains:
    #
    # runner -> set(slot indexes)
    #
    # Example:
    #
    # Shadow:
    # {0,1,2}
    #
    # preferred:
    # {1}
    #
    # If a runner has:
    #
    # 15:00
    # 16:30
    # 18:00
    #
    # 16:30 receives no penalty.
    #
    # 15:00 and 18:00 receive +1.
    #
    # This only affects equal-score solutions.
    # ------------------------------------------------


    for r, match in enumerate(match_data):


        runner1 = match["runner1"]

        runner2 = match["runner2"]



        preferred1 = preferred_slots.get(
            runner1,
            set()
        )


        preferred2 = preferred_slots.get(
            runner2,
            set()
        )



        for s in match["possible_slots"]:


            race_here = race_in_slot[r][s]



            # Runner 1

            if s not in preferred1:

                objective.append(
                    PREFERRED_SLOT_PENALTY
                    *
                    race_here
                )



            # Runner 2

            if s not in preferred2:

                objective.append(
                    PREFERRED_SLOT_PENALTY
                    *
                    race_here
                )

    # ------------------------------------------------
    # Minimize total objective
    # ------------------------------------------------

    model.Minimize(
        sum(objective)
    )



    # ------------------------------------------------
    # Return model objects
    # ------------------------------------------------

    return {

        "model":
            model,

        "race_slot":
            race_slot,

        "prerec_flags":
            prerec_flags,

        "race_in_slot":
            race_in_slot,

        "slot_used":
            slot_used

    }