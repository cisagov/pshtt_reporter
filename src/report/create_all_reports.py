#!/usr/bin/env python3
"""Generate all reports."""

# Standard Python Libraries
import csv
import os

HOME_DIR = "/home/cisa"
SHARED_DATA_DIR = HOME_DIR + "/shared/"


def main():
    """Generate all reports."""
    with open(SHARED_DATA_DIR + "artifacts/unique-agencies.csv") as agency_csv:
        for row in sorted(csv.reader(agency_csv)):
            bashCommand = (
                HOME_DIR + "/report/generate_https_scan_report.py " + '"' + row[0] + '"'
            )
            # generate_https_scan_report.py isn't written in a way
            # that easily allows it to be run in any other way.  Hence
            # the nosec.
            os.system(bashCommand)  # nosec B605


if __name__ == "__main__":
    main()
