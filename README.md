# Scheduling Tool

This project schedules race matchups based on runner availability and preferred slots.

The schedule covers Monday through Friday. Starts may occur at the beginning of
any UTC hour. Each match lasts three hours and is followed by a one-hour break,
so race starts must be at least four hours apart.

## Features

- Loads runner availability data from CSV files
- Builds a scheduling model for race slots
- Writes the resulting schedule to schedule.csv

## Availability format

`availabilities.csv` should contain `runner` plus `monday` through `friday`
columns. Each day contains comma-separated UTC start times such as
`14:00 UTC, 15:00 UTC, 16:00 UTC`. Empty cells and `Nothing` mean that the
runner is unavailable that day. A `timezone` column is optional; when present,
times are converted to UTC.

## Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

## Usage

Run the scheduling workflow:

```bash
python scheduling_tool.py
```

Run the regression tests:

```bash
python -m unittest discover -s tests -v
```
