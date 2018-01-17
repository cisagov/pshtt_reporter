#!/usr/bin/env python3

import os
import csv

SHARED_DATA_DIR = '/home/shared/'

def main():
    agency_csv = open(SHARED_DATA_DIR + "artifacts/unique-agencies.csv")

    for row in sorted(csv.reader(agency_csv)):
        bashCommand = "/home/scanner/report/generate_https_scan_report.py " + '"' + row[0] + '"'
        os.system(bashCommand)

if __name__ == "__main__":
    main()
