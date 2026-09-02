# scheduling_tool.py

import pandas as pd
from ortools.sat.python import cp_model


from parser import (
    load_availability,
    load_matchups,
    create_slot_lookup,
    display_time,
    DAYS,
    UTC_SLOTS
)


from model import (
    build_model
)


from output import (
    display_solutions
)


from scoring import (
    calculate_score
)


# ----------------------------------------------------
# Files
# ----------------------------------------------------

MATCHUPS_FILE = "matchups.csv"
AVAIL_FILE = "availabilities.csv"

OUTPUT_FILE = "schedule.csv"



# ----------------------------------------------------
# Configuration
# ----------------------------------------------------

TOP_SOLUTIONS = 3



SLOTS_PER_DAY = len(
    UTC_SLOTS
)



# ----------------------------------------------------
# Load data
# ----------------------------------------------------

availability = load_availability(
    AVAIL_FILE
)

print(
    "Loaded runners:"
)

print(
    list(availability.keys())
)


matches = load_matchups(
    MATCHUPS_FILE
)



# ----------------------------------------------------
# Create slots
# ----------------------------------------------------

slot_lookup, all_slots = create_slot_lookup()



NUM_SLOTS = len(
    all_slots
)



# ----------------------------------------------------
# Prepare matchup data
# ----------------------------------------------------

match_data = []

def preferred_slot_indices(slots):

    if not slots:
        return set()

    slots = sorted(slots)

    preferred = set()

    i = 0

    while i < len(slots):

        group = [slots[i]]

        i += 1

        while i < len(slots) and slots[i] == group[-1] + 1:
            group.append(slots[i])
            i += 1


        length = len(group)


        if length == 1:
            preferred.add(group[0])

        elif length == 2:
            preferred.add(group[0])
            preferred.add(group[1])

        else:
            middle = length // 2

            preferred.add(group[middle])

            if length % 2 == 0:
                preferred.add(group[middle - 1])


    return preferred

runner_preferred_slots = {
    runner: preferred_slot_indices(
        {
            slot_lookup[x]
            for x in slots
            if x in slot_lookup
        }
    )
    for runner, slots in availability.items()
}

for _, row in matches.iterrows():


    r1 = row["runner1"]

    r2 = row["runner2"]

    missing_availability_runners = []



    if r1 not in availability:
        availability[r1] = set()
        runner_preferred_slots[r1] = set()
        missing_availability_runners.append(r1)
        print(
            f"Warning: {r1} missing from availability; "
            "treating as empty availability"
        )


    if r2 not in availability:
        availability[r2] = set()
        runner_preferred_slots[r2] = set()
        missing_availability_runners.append(r2)
        print(
            f"Warning: {r2} missing from availability; "
            "treating as empty availability"
        )



    r1_slots = {
        slot_lookup[x]
        for x in availability[r1]
        if x in slot_lookup
    }



    r2_slots = {
        slot_lookup[x]
        for x in availability[r2]
        if x in slot_lookup
    }

    r1_preferred = preferred_slot_indices(r1_slots)

    r2_preferred = preferred_slot_indices(r2_slots)



    possible_slots = (
        r1_slots
        |
        r2_slots
    )



    if not possible_slots:
        # No runner availability at all for this matchup.
        # Allow any slot; model objectives will keep it prerecorded
        # and push it as late as possible.
        possible_slots = set(
            range(NUM_SLOTS)
        )

        print(
            f"Warning: {r1} vs {r2} has no availability; "
            "forcing prerecorded late placement"
        )



    match_data.append(
        {
            "runner1": r1,

            "runner2": r2,

            "r1_slots": r1_slots,

            "r2_slots": r2_slots,

            "r1_preferred": r1_preferred,

            "r2_preferred": r2_preferred,

            "missing_availability_runners": missing_availability_runners,

            "possible_slots": list(possible_slots)
        }
    )



print()

print(
    f"Loaded {len(match_data)} matches"
)



# ----------------------------------------------------
# Build optimization model
# ----------------------------------------------------

model_data = build_model(
    match_data,
    NUM_SLOTS,
    SLOTS_PER_DAY,
    runner_preferred_slots,
    all_slots
)



model = model_data["model"]


race_slot = model_data["race_slot"]


prerec_flags = model_data["prerec_flags"]



# ----------------------------------------------------
# Helper: extract solution
# ----------------------------------------------------

def extract_solution(
    solver
):

    data = []


    for i, slot_var in enumerate(
        race_slot
    ):


        data.append(
            {
                "race":
                    i,

                "slot":
                    solver.Value(
                        slot_var
                    ),

                "p1_prerec":
                    bool(
                        solver.Value(
                            prerec_flags[i*2]
                        )
                    ),

                "p2_prerec":
                    bool(
                        solver.Value(
                            prerec_flags[i*2+1]
                        )
                    )
            }
        )


    return data



# ----------------------------------------------------
# Solve first optimal solution
# ----------------------------------------------------

solutions = []



solver = cp_model.CpSolver()


solver.parameters.num_search_workers = 4


solver.parameters.max_time_in_seconds = 20

solver.parameters.random_seed = 0



status = solver.Solve(
    model
)



if status not in (
    cp_model.OPTIMAL,
    cp_model.FEASIBLE
):

    raise Exception(
        "No solution found"
    )



first_solution_data = extract_solution(
    solver
)

first_solution = {
    "data":
        first_solution_data,

    "objective":
        solver.ObjectiveValue(),
}



solutions.append(
    first_solution
)
# ----------------------------------------------------
# Find additional solutions
# ----------------------------------------------------

for solution_number in range(
    2,
    TOP_SOLUTIONS + 1
):

    previous = solutions[-1]["data"]

    differences = []


    # Different race slots

    for i, slot_var in enumerate(race_slot):

        diff = model.NewBoolVar(
            f"different_slot_{solution_number}_{i}"
        )


        model.Add(
            slot_var != previous[i]["slot"]
        ).OnlyEnforceIf(
            diff
        )


        model.Add(
            slot_var == previous[i]["slot"]
        ).OnlyEnforceIf(
            diff.Not()
        )


        differences.append(
            diff
        )



    # Different prerecorded flags

    for i in range(len(match_data)):

        p1 = prerec_flags[i * 2]
        p2 = prerec_flags[i * 2 + 1]


        diff_p1 = model.NewBoolVar(
            f"different_p1_{solution_number}_{i}"
        )


        if previous[i]["p1_prerec"]:

            model.Add(
                p1 == 0
            ).OnlyEnforceIf(
                diff_p1
            )

            model.Add(
                p1 == 1
            ).OnlyEnforceIf(
                diff_p1.Not()
            )

        else:

            model.Add(
                p1 == 1
            ).OnlyEnforceIf(
                diff_p1
            )

            model.Add(
                p1 == 0
            ).OnlyEnforceIf(
                diff_p1.Not()
            )


        differences.append(
            diff_p1
        )



        diff_p2 = model.NewBoolVar(
            f"different_p2_{solution_number}_{i}"
        )


        if previous[i]["p2_prerec"]:

            model.Add(
                p2 == 0
            ).OnlyEnforceIf(
                diff_p2
            )

            model.Add(
                p2 == 1
            ).OnlyEnforceIf(
                diff_p2.Not()
            )

        else:

            model.Add(
                p2 == 1
            ).OnlyEnforceIf(
                diff_p2
            )

            model.Add(
                p2 == 0
            ).OnlyEnforceIf(
                diff_p2.Not()
            )


        differences.append(
            diff_p2
        )



    # Require at least one difference

    model.AddBoolOr(
        differences
    )


    solver = cp_model.CpSolver()

    solver.parameters.num_search_workers = 4

    solver.parameters.max_time_in_seconds = 15

    solver.parameters.random_seed = 0



    status = solver.Solve(
        model
    )


    if status not in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE
    ):

        break



    solution_data = extract_solution(
        solver
    )

    solutions.append(
        {
            "data":
                solution_data,

            "objective":
                solver.ObjectiveValue(),
        }
    )


# ----------------------------------------------------
# Rank by the user-readable penalty score
# ----------------------------------------------------

for solution in solutions:

    solution["readable_score"] = calculate_score(
        solution,
        match_data,
        runner_preferred_slots,
        NUM_SLOTS,
        SLOTS_PER_DAY
    )["score"]

solutions = sorted(
    solutions,
    key=lambda x:
        x["readable_score"]
)



print()

print(
    f"Collected {len(solutions)} solutions"
)



for i, solution in enumerate(
    solutions,
    start=1
):

    print(
        f"Solution {i}: "
        f"readable_score={solution['readable_score']} "
        f"solver_objective={solution['objective']}"
    )



# ----------------------------------------------------
# Display and save
# ----------------------------------------------------

display_solutions(
    solutions,

    match_data,

    all_slots,

    display_time,

    SLOTS_PER_DAY,

    OUTPUT_FILE,

    runner_preferred_slots
)

print()
print(
    "Solver status:",
    solver.StatusName(status)
)