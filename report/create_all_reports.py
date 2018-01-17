#!/usr/bin/env python3

import os
import csv

HOME_DIR = '/home/reporter'
SHARED_DATA_DIR = HOME_DIR + '/shared/'

def main():
    agency_csv = open(SHARED_DATA_DIR + "artifacts/unique-agencies.csv")

    for row in sorted(csv.reader(agency_csv)):
        bashCommand = HOME_DIR + "/report/generate_https_scan_report.py " + '"' + row[0] + '"'
        os.system(bashCommand)

if __name__ == "__main__":
    main()
