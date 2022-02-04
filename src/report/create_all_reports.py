#!/usr/bin/env python3
"""Generate all reports."""

# Standard Python Libraries
import csv

# generate_https_scan_report.py isn't written in a way that easily
# allows it to be run in any other way, but Bandit doesn't like us to
# use subprocess.  Hence the nosec.
import subprocess  # nosec B404

HOME_DIR = "/home/cisa"
SHARED_DATA_DIR = HOME_DIR + "/shared/"


def main():
    """Generate all reports."""
    with open(SHARED_DATA_DIR + "artifacts/unique-agencies.csv") as agency_csv:
        for row in sorted(csv.reader(agency_csv)):
            bashCommand = [f"{HOME_DIR}/report/generate_https_scan_report.py", row[0]]
            # generate_https_scan_report.py isn't written in a way
            # that easily allows it to be run in any other way, but
            # Bandit doesn't like us to use subprocess.  Hence the
            # nosec.
            subprocess.run(bashCommand)  # nosec B404


if __name__ == "__main__":
    main()
