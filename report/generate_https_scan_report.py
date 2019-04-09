#!/usr/bin/env python3

'''Create Cyber Hygiene HTTPS Report PDF.

Usage:
  generate_https_scan_report [options] "AGENCY"
  generate_https_scan_report (-h | --help)
  generate_https_scan_report --version

Options:
  -d --debug                     Keep intermediate files for debugging.
  -h --help                      Show this screen.
  --version                      Show version.
'''
# standard python libraries
import codecs
import csv
from datetime import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

# third-party libraries (install with pip)
from docopt import docopt
from mongo_db_from_config import db_from_config
import pystache

# intra-project modules
import graphs

# constants
HOME_DIR = '/home/reporter'
SHARED_DATA_DIR = HOME_DIR + '/shared/'
DB_CONFIG_FILE = '/run/secrets/scan_read_creds.yml'
HTTPS_RESULTS_CSV_FILE = 'pshtt-results.csv'
OCSP_EXCLUSION_CSV_FILE = SHARED_DATA_DIR + 'artifacts/ocsp-crl.csv'
# Do not include the orgs below (based on _id) in the Report
EXEMPT_ORGS = []
MUSTACHE_FILE = 'https_scan_report.mustache'
REPORT_JSON = 'https_scan_report.json'
REPORT_PDF = 'https_scan_report.pdf'
REPORT_TEX = 'https_scan_report.tex'
ASSETS_DIR_SRC = '../assets'
ASSETS_DIR_DST = 'assets'
LATEX_ESCAPE_MAP = {
    '$': '\\$',
    '%': '\\%',
    '&': '\\&',
    '#': '\\#',
    '_': '\\_',
    '{': '\\{',
    '}': '\\}',
    '[': '{[}',
    ']': '{]}',
    "'": "{'}",
    '\\': '\\textbackslash{}',
    '~': '\\textasciitilde{}',
    '<': '\\textless{}',
    '>': '\\textgreater{}',
    '^': '\\textasciicircum{}',
    '`': '{}`',
    '\n': '\\newline{}',
}
PDF_CAPTURE_JS = 'pdf_capture.js'


class ReportGenerator(object):
    # initiate variables
    def __init__(self, db, agency, debug=False):
        self.__db = db
        self.__agency = agency
        self.__agency_id = None
        self.__debug = debug
        self.__generated_time = datetime.utcnow()
        self.__results = dict()  # reusable query results
        self.__requests = None
        self.__report_doc = {'scores': []}
        self.__all_domains = []
        self.__base_domains = []
        self.__eligible_domains_count = 0  # second-level/base-domains
        self.__eligible_subdomains_count = 0
        self.__all_eligible_domains_count = 0  # responsive base+subs
        self.__https_compliance_list = []
        self.__non_https_compliance_list = []
        self.__ineligible_domains = []
        self.__domain_count = 0
        self.__base_domain_count = 0
        self.__subdomain_count = 0
        self.__domain_supports_https = 0
        self.__domain_supports_https_count = 0
        self.__domain_enforces_https_count = 0  # added
        self.__domain_uses_strong_hsts_count = 0
        self.__domain_has_no_weak_crypto_count = 0
        self.__strictly_forces_count = 0
        self.__downgrades_count = 0
        self.__hsts_count = 0
        self.__hsts_preloaded_count = 0
        self.__hsts_preload_ready_count = 0
        self.__hsts_entire_domain_count = 0
        self.__https_bad_chain_count = 0
        self.__https_bad_hostname_count = 0
        self.__https_expired_cert_count = 0
        self.__bod_1801_count = 0
        self.__hsts_base_domain_preloaded_count = 0
        self.__hsts_low_max_age_count = 0
        # self.__report_oid = ObjectId()

        # Read in and parse the OCSP exclusion domains.
        #
        # We use a dict for ocsp_exclusions because we want to take
        # advantage of the speed of the underlying hash map.  (We only
        # care if a domain is present as an exclusion or not.)
        ocsp_exclusions = {}
        with open(OCSP_EXCLUSION_CSV_FILE, newline='') as ocsp_file:
            csvreader = csv.reader(ocsp_file)
            ocsp_exclusions = {row[0]: None for row in csvreader}

        # Get list of all domains from the database
        all_domains_cursor = self.__db.https_scan.find({
            'latest': True,
            'agency.name': agency
        })
        # We really shouldn't include OCSP excluded domains in the
        # total count.  We do want to score them, for informational
        # purposes, but the scores will not impact compliance.
        # Therefore I should really perform this query:
        #   self.__domain_count = self.__db.https_scan.count({
        #       'latest': True,
        #       'agency.name': agency,
        #       'domain': {
        #            '$nin': ocsp_exclusions.keys()
        #        }
        #   })
        #
        # In reality this value is not used in the report at all, so
        # it doesn't matter.
        self.__domain_count = all_domains_cursor.count()

        # Get weak crypto data for this agency's domains from the
        # sslyze-scan collection
        #
        # TODO: Consider using aggregation $lookup with uncorrelated
        # subquery to fetch https_scan and sslyze_scan data in one
        # query (MongoDB server 3.6 and later)

        sslyze_data_all_domains = dict()
        for host in self.__db.sslyze_scan.find(
            {
                'latest': True,
                'agency.name': agency,
                'scanned_port': 443
            }, {
                '_id': 0,
                'domain': 1,
                'scanned_port': 1,
                'scanned_hostname': 1,
                'sslv2': 1,
                'sslv3': 1,
                'any_3des': 1,
                'any_rc4': 1,
                'is_symantec_cert': 1
            }
        ):
            current_host_dict = {
                'scanned_hostname': host['scanned_hostname'],
                'scanned_port': host['scanned_port'],
                'sslv2': host['sslv2'],
                'sslv3': host['sslv3'],
                'any_3des': host['any_3des'],
                'any_rc4': host['any_rc4'],
                'is_symantec_cert': host['is_symantec_cert']
            }

            if not sslyze_data_all_domains.get(host['domain']):
                sslyze_data_all_domains[host['domain']] = [current_host_dict]
            else:
                sslyze_data_all_domains[host['domain']].append(
                    current_host_dict
                )

        def add_weak_crypto_data_to_domain(domain_doc,
                                           sslyze_data_all_domains):
            # Look for weak crypto data in sslyze_data_all_domains and
            # add hosts with weak crypto to
            # domain_doc['hosts_with_weak_crypto']
            domain_doc['domain_has_weak_crypto'] = False
            domain_doc['hosts_with_weak_crypto'] = []
            domain_doc['domain_has_symantec_cert'] = False

            if sslyze_data_all_domains.get(domain_doc['domain']):
                for host in sslyze_data_all_domains[domain_doc['domain']]:
                    if host['sslv2'] or host['sslv3'] or \
                       host['any_3des'] or host['any_rc4']:
                        domain_doc['domain_has_weak_crypto'] = True
                        domain_doc['hosts_with_weak_crypto'].append(host)
                    if host['is_symantec_cert']:
                        domain_doc['domain_has_symantec_cert'] = True
            return domain_doc

        for domain_doc in all_domains_cursor:
            domain_doc = add_weak_crypto_data_to_domain(
                domain_doc,
                sslyze_data_all_domains
            )
            domain_doc['ocsp_domain'] = domain_doc['domain'] in ocsp_exclusions
            self.__all_domains.append(domain_doc)
            if domain_doc['is_base_domain']:
                domain_doc['subdomains'] = list(self.__db.https_scan.find({
                    'latest': True,
                    'base_domain': domain_doc['base_domain'],
                    'is_base_domain': False
                }).sort([('domain', 1)]))
                self.__subdomain_count += len(domain_doc['subdomains'])
                for subdomain_doc in domain_doc['subdomains']:
                    subdomain_doc = add_weak_crypto_data_to_domain(
                        subdomain_doc,
                        sslyze_data_all_domains
                    )
                    subdomain_doc['ocsp_domain'] = \
                        subdomain_doc['domain'] in ocsp_exclusions
                self.__base_domains.append(domain_doc)
            self.__agency_id = domain_doc['agency']['id']

        # Get a count of the second-level domains an agency owns.
        #
        # Really I should exclude OCSP domains here, but this isn't
        # necessary since OCSP domains should be individual hostnames
        # and not second-level domains.
        self.__base_domain_count = self.__db.https_scan.find({
            'latest': True,
            'agency.name': agency,
            'is_base_domain': True
        }).count()

    def __score_domain(self, domain):
        score = {
            'domain': domain['domain'],
            'ocsp_domain': domain['ocsp_domain'],
            'subdomain_scores': list()
        }

        if domain['live']:
            score['live_bool'] = True
            # OCSP domains aren't eligible
            if not domain['ocsp_domain']:
                if domain['is_base_domain']:
                    self.__eligible_domains_count += 1
                    self.__all_eligible_domains_count += 1
                else:
                    self.__eligible_subdomains_count += 1
                    self.__all_eligible_domains_count += 1
            else:
                # TODO Determine if this is still needed
                self.__ineligible_domains.append({
                    'domain': domain['domain']
                })
        else:
            score['live_bool'] = False
            if domain['is_base_domain']:
                # only include non-live base domains in the ineligible
                # domains list; otherwise lots of non-existent subs
                # will show in the report

                # TODO Determine if this is still needed
                self.__ineligible_domains.append({
                    'domain': domain['domain']
                })

        # https_full_connection and https_client_auth_required
        if domain['https_full_connection']:
            score['https_full_connection_bool'] = True
        else:
            score['https_full_connection_bool'] = False
        if domain['https_client_auth_required']:
            score['https_client_auth_required_bool'] = True
        else:
            score['https_client_auth_required_bool'] = False

        # strictly_forces_https
        if domain['strictly_forces_https']:
            # score['strictly_forces_https'] = 'Yes'
            score['strictly_forces_https_bool'] = True
            if not domain['ocsp_domain']:
                self.__strictly_forces_count += 1
        else:
            # score['strictly_forces_https'] = 'No'
            score['strictly_forces_https_bool'] = False

        # "Uses HTTPS", domains_supports_https
        #
        # Domain gets credit for supporting HTTPS as long as it's live
        # and hsts_base_domain_preloaded is true
        if domain['domain_supports_https'] or \
           (domain['live'] and domain['hsts_base_domain_preloaded']):
            # score['domain_supports_https'] = 'Yes'
            score['domain_supports_https_bool'] = True
            if not domain['ocsp_domain']:
                self.__domain_supports_https_count += 1
        else:
            # score['domain_supports_https'] = 'No'
            score['domain_supports_https_bool'] = False

        # "Enforces HTTPS", domain_enforces_https
        #
        # Domain gets credit for enforcing HTTPS as long as it's live
        # and hsts_base_domain_preloaded is true
        if domain['domain_enforces_https'] or \
           (domain['live'] and domain['hsts_base_domain_preloaded']):
            # score['domain_enforces_https'] = 'Yes'
            score['domain_enforces_https_bool'] = True
            if not domain['ocsp_domain']:
                self.__domain_enforces_https_count += 1
        else:
            # score['domain_enforces_https'] = 'No'
            score['domain_enforces_https_bool'] = False

        # https_bad_chain
        if domain['https_bad_chain'] and domain['https_bad_hostname']:
            score['https_bad_chain_bool'] = True
            if not domain['ocsp_domain']:
                self.__https_bad_chain_count += 1
        elif (domain['https_bad_chain'] and
              not domain['https_bad_hostname']) or \
             (domain['https_bad_chain'] and domain['https_expired_cert']):
            if not domain['ocsp_domain']:
                self.__https_bad_chain_count += 1
        else:
            score['https_bad_chain_bool'] = False

        # https_bad_hostname
        if domain['https_bad_hostname']:
            score['https_bad_hostname_bool'] = True
            if not domain['ocsp_domain']:
                self.__https_bad_hostname_count += 1
        else:
            score['https_bad_hostname_bool'] = False

        # https_expired_cert
        if domain['https_expired_cert']:
            score['https_expired_cert_bool'] = True
            if not domain['ocsp_domain']:
                self.__https_expired_cert_count += 1
        else:
            score['https_expired_cert_bool'] = False

        # redirect
        if domain['redirect']:
            score['redirect_bool'] = True
        else:
            score['redirect_bool'] = False

        # downgrades_https
        if domain['downgrades_https']:
            # score['downgrades_https'] = 'Yes'
            score['downgrades_https_bool'] = True
            if not domain['ocsp_domain']:
                self.__downgrades_count += 1
        else:
            # score['downgrades_https'] = 'No'
            score['downgrades_https_bool'] = False

        # Is the domain's base_domain preloaded?
        # In this case, we only care if the domain is live
        if domain['live'] and domain['hsts_base_domain_preloaded']:
            score['hsts_base_domain_preloaded_bool'] = True
            if not domain['ocsp_domain']:
                self.__hsts_base_domain_preloaded_count += 1
        else:
            score['hsts_base_domain_preloaded'] = False

        # is HSTS present?
        if domain['hsts']:
            # score['hsts'] = 'Yes'
            score['hsts_bool'] = True

            # hsts_preloaded > hsts_preload_pending > hsts_preload_ready
            if domain['hsts_preloaded']:
                # score['hsts_preloaded'] = 'Yes'
                score['hsts_preloaded_bool'] = True
                if not domain['ocsp_domain']:
                    self.__hsts_preloaded_count += 1
            else:
                score['hsts_preloaded_bool'] = False
                # score['hsts_preloaded'] = 'No'
                if domain['hsts_preload_pending']:
                    score['hsts_preload_pending_bool'] = True
                else:
                    score['hsts_preload_pending_bool'] = False

                if domain['hsts_preload_ready']:
                    score['hsts_preload_ready_bool'] = True
                    # score['hsts_preload_ready'] = 'Yes'
                    if not domain['ocsp_domain']:
                        self.__hsts_preload_ready_count += 1
                else:
                    score['hsts_preload_ready_bool'] = False
                    # score['hsts_preload_ready'] = 'No'

            # HTTPS Strict Transport Security (HSTS): This is 'Yes' in
            # the report only if HSTS is present and the max-age is >=
            # 1 year, as BOD 18-01 requires
            #
            # Domain gets credit for strong HSTS as long as it's live
            # and hsts_base_domain_preloaded is true
            if domain['domain_uses_strong_hsts'] or \
               (domain['live'] and domain['hsts_base_domain_preloaded']):
                score['domain_uses_strong_hsts_bool'] = True
                if not domain['ocsp_domain']:
                    self.__domain_uses_strong_hsts_count += 1
            else:
                score['domain_uses_strong_hsts_bool'] = False
                if 0 < domain['hsts_max_age'] < 31536000:
                    if not domain['ocsp_domain']:
                        self.__hsts_low_max_age_count += 1
        elif domain['live'] and (
                domain['hsts_base_domain_preloaded'] or
                (not domain['https_full_connection'] and
                 domain['https_client_auth_required'])
        ):
            # If HSTS is not present but the base_domain is preloaded,
            # "HSTS" gets a thumbs up.  In this case, we only care if
            # the domain is live.
            #
            # If we can't make a full HTTPS connection because the
            # domain requires client authentication, then we can't
            # know if they serve HSTS headers or not.  We have to give
            # them the benefit of the doubt.
            score['domain_uses_strong_hsts_bool'] = True
            if not domain['ocsp_domain']:
                self.__domain_uses_strong_hsts_count += 1
        else:
            # No HSTS
            # score['hsts'] = 'No'
            score['hsts_bool'] = False
            score['hsts_preloaded_bool'] = False
            score['hsts_preload_pending_bool'] = False
            score['hsts_preload_ready_bool'] = False
            score['domain_uses_strong_hsts_bool'] = False

        # Does the domain have weak crypto?
        score['domain_has_weak_crypto_bool'] = domain['domain_has_weak_crypto']
        if domain['live'] and not domain['domain_has_weak_crypto']:
            if not domain['ocsp_domain']:
                self.__domain_has_no_weak_crypto_count += 1
        # Build list of weak crypto host info and save it in
        # score['hosts_with_weak_crypto']
        score['hosts_with_weak_crypto'] = list()
        for host in domain['hosts_with_weak_crypto']:
            weak_crypto_list = list()
            for (wc_key, wc_text) in [
                    ('sslv2', 'SSLv2'),
                    ('sslv3', 'SSLv3'),
                    ('any_3des', '3DES'),
                    ('any_rc4', 'RC4')
            ]:
                if host[wc_key]:
                    weak_crypto_list.append(wc_text)
            score['hosts_with_weak_crypto'].append({
                'hostname': host['scanned_hostname'],
                'port': host['scanned_port'],
                'weak_crypto_list_str': ', '.join(weak_crypto_list)
            })

        # Does the domain have a Symantec cert?
        # If so, they have to be replaced - see:
        #  https://www.symantec.com/connect/blogs/information-replacement-symantec-ssltls-certificates
        score['domain_has_symantec_cert_bool'] = \
            domain['domain_has_symantec_cert']

        # BOD 18-01 compliant?
        if (
                (domain['domain_supports_https'] and
                 domain['domain_enforces_https'] and
                 domain['domain_uses_strong_hsts']) or
                (domain['live'] and domain['hsts_base_domain_preloaded'])
        ) and not domain['domain_has_weak_crypto']:
            score['bod_1801_compliance'] = True
            if not domain['ocsp_domain']:
                self.__bod_1801_count += 1
        else:
            score['bod_1801_compliance'] = False

        if domain.get('subdomains'):    # if this domain has any subdomains
            for subdomain in domain['subdomains']:
                subdomain_score = self.__score_domain(subdomain)
                if subdomain_score['live_bool']:    # Only add live
                    # subdomains add this subdomain's score to this
                    # domain's list of subdomain_scores
                    score['subdomain_scores'].append(subdomain_score)
        return score

    def __populate_report_doc(self):
        # index = 0
        # sort list of all domains
        self.__all_domains.sort(key=lambda x: x['domain'])
        # sort list of base domains
        self.__base_domains.sort(key=lambda x: x['domain'])

        # Go through each base domain and score the attributes
        for domain in self.__base_domains:
            score = self.__score_domain(domain)
            # Add domain's score to master list of scores
            self.__report_doc['scores'].append(score)

        if not self.__all_eligible_domains_count:
            # TODO Decide if we want to generate an empty report in this case
            print('ERROR: "{}" has no live domains - exiting without generating report!'.format(self.__agency))
            sys.exit(-1)

        self.__uses_https_percentage = round(
            self.__domain_supports_https_count /
            self.__all_eligible_domains_count * 100.0,
            1
        )
        self.__enforces_https_percentage = round(
            self.__domain_enforces_https_count /
            self.__all_eligible_domains_count * 100.0,
            1
        )
        self.__hsts_percentage = round(
            self.__domain_uses_strong_hsts_count /
            self.__all_eligible_domains_count * 100.0,
            1
        )
        self.__has_no_weak_crypto_percentage = round(
            self.__domain_has_no_weak_crypto_count /
            self.__all_eligible_domains_count * 100,
            1
        )
        self.__bod_1801_percentage = round(
            self.__bod_1801_count /
            self.__all_eligible_domains_count * 100.0,
            1
        )

        # self.__write_to_overview() # generates ARTIFACTS_DIR +
        # "/reporting.csv" - is this still needed?

    def __latex_escape(self, to_escape):
        return ''.join([LATEX_ESCAPE_MAP.get(i, i) for i in to_escape])

    def __latex_escape_structure(self, data):
        '''assumes that all sequences contain dicts'''
        if isinstance(data, dict):
            for k, v in data.items():
                if k.endswith('_tex'):  # skip special tex values
                    continue
                if isinstance(v, str):
                    data[k] = self.__latex_escape(v)
                else:
                    self.__latex_escape_structure(v)
        elif isinstance(data, (list, tuple)):
            for i in data:
                self.__latex_escape_structure(i)

    def generate_https_scan_report(self):
        print('\tParsing data')
        # build up the report_doc from the query results
        self.__populate_report_doc()

        # sort org lists
        if self.__https_compliance_list:
            self.__https_compliance_list.sort(key=lambda x: x['domain'])
        if self.__non_https_compliance_list:
            self.__non_https_compliance_list.sort(key=lambda x: x['domain'])

        # create a working directory
        original_working_dir = os.getcwd()
        if self.__debug:
            temp_working_dir = tempfile.mkdtemp(dir=original_working_dir)
        else:
            temp_working_dir = tempfile.mkdtemp()

        # setup the working directory
        self.__setup_work_directory(temp_working_dir)
        os.chdir(temp_working_dir)

        print('\tGenerating attachments')
        # generate attachments
        self.__generate_attachments()

        print('\tGenerating charts')
        # generate charts
        self.__generate_charts()

        # generate json input to mustache
        self.__generate_mustache_json(REPORT_JSON)

        # generate latex json + mustache
        self.__generate_latex(MUSTACHE_FILE, REPORT_JSON, REPORT_TEX)

        print('\tAssembling PDF')
        # generate report figures + latex
        self.__generate_final_pdf()

        # revert working directory
        os.chdir(original_working_dir)

        # copy report and json file to original working directory
        # and delete working directory
        if not self.__debug:
            src_filename = os.path.join(temp_working_dir, REPORT_PDF)
            datestamp = self.__generated_time.strftime('%Y-%m-%d')
            dest_dir = "."

            if self.__agency_id is not None:
                dest_filename = "{}/cyhy-{}-{}-https-report.pdf".format(
                                    dest_dir, self.__agency_id, datestamp)
            else:
                dest_filename = "{}/cyhy-{}-{}-https-report.pdf".format(
                                    dest_dir, self.__agency, datestamp)

            shutil.move(src_filename, dest_filename)
        return self.__results

    def __setup_work_directory(self, work_dir):
        me = os.path.realpath(__file__)
        my_dir = os.path.dirname(me)
        for n in (MUSTACHE_FILE, PDF_CAPTURE_JS):
            file_src = os.path.join(my_dir, n)
            file_dst = os.path.join(work_dir, n)
            shutil.copyfile(file_src, file_dst)
        # copy static assets
        dir_src = os.path.join(my_dir, ASSETS_DIR_SRC)
        dir_dst = os.path.join(work_dir, ASSETS_DIR_DST)
        shutil.copytree(dir_src, dir_dst)

    ###########################################################################
    #  Attachment Generation
    ###########################################################################
    def __generate_attachments(self):
        self.__generate_https_attachment()

    def __generate_https_attachment(self):
        header_fields = ('Domain', 'Base Domain', 'Domain Is Base Domain',
                         'Canonical URL', 'Live', 'Redirect', 'Redirect To',
                         'Valid HTTPS', 'Defaults to HTTPS',
                         'Downgrades HTTPS', 'Strictly Forces HTTPS',
                         'HTTPS Bad Chain', 'HTTPS Bad Hostname',
                         'HTTPS Expired Cert', 'HTTPS Self Signed Cert',
                         'HSTS', 'HSTS Header', 'HSTS Max Age',
                         'HSTS Entire Domain', 'HSTS Preload Ready',
                         'HSTS Preload Pending', 'HSTS Preloaded',
                         'Base Domain HSTS Preloaded',
                         'Domain Supports HTTPS', 'Domain Enforces HTTPS',
                         'Domain Uses Strong HSTS',
                         'HTTPS Client Auth Required',
                         'Domain Supports Weak Crypto',
                         'Web Hosts With Weak Crypto',
                         'Domain Uses Symantec Certificate',
                         'OCSP Domain', 'Unknown Error')
        data_fields = ('domain', 'base_domain', 'is_base_domain',
                       'canonical_url', 'live', 'redirect', 'redirect_to',
                       'valid_https', 'defaults_https',
                       'downgrades_https', 'strictly_forces_https',
                       'https_bad_chain', 'https_bad_hostname',
                       'https_expired_cert', 'https_self_signed_cert',
                       'hsts', 'hsts_header', 'hsts_max_age',
                       'hsts_entire_domain', 'hsts_preload_ready',
                       'hsts_preload_pending', 'hsts_preloaded',
                       'hsts_base_domain_preloaded',
                       'domain_supports_https', 'domain_enforces_https',
                       'domain_uses_strong_hsts',
                       'https_client_auth_required',
                       'domain_has_weak_crypto',
                       'hosts_with_weak_crypto_str',
                       'domain_has_symantec_cert',
                       'ocsp_domain', 'unknown_error')
        with open(HTTPS_RESULTS_CSV_FILE, newline='', mode='w') as out_file:
            header_writer = csv.DictWriter(out_file, header_fields,
                                           extrasaction='ignore')
            header_writer.writeheader()
            data_writer = csv.DictWriter(out_file, data_fields,
                                         extrasaction='ignore')

            def rehydrate_hosts_with_weak_crypto(d):
                """Build a string suitable for output from the
                dictionary that was retrieved from the database

                Parameters
                ----------
                d : dict
                    The hosts_with_weak_crypto dictionary

                Returns
                -------
                str: The string with weak crypto host details.
                """
                hostname = d['scanned_hostname']
                port = d['scanned_port']

                weak_crypto_list = list()
                for (wc_key, wc_text) in [
                        ('sslv2', 'SSLv2'),
                        ('sslv3', 'SSLv3'),
                        ('any_3des', '3DES'),
                        ('any_rc4', 'RC4')
                ]:
                    if d[wc_key]:
                        weak_crypto_list.append(wc_text)
                result = '{0}:{1} [supports: {2}]'.format(
                    hostname, port, ','.join(weak_crypto_list)
                )

                return result

            def format_list(record_list):
                """Format a list into a string to increase readability
                in CSV"""
                # record_list should only be a list, not an integer, None, or
                # anything else.  Thus this if clause handles only empty lists.
                # This makes a "null" appear in the JSON output for empty
                # lists, as expected.
                if not record_list:
                    return None

                return ', '.join(record_list)

            for domain in self.__all_domains:
                hosts_with_weak_crypto = [
                    rehydrate_hosts_with_weak_crypto(d)
                    for d in domain['hosts_with_weak_crypto']
                ]
                domain['hosts_with_weak_crypto_str'] = format_list(
                    hosts_with_weak_crypto
                )
                data_writer.writerow(domain)

    ###########################################################################
    #  Chart Generation
    ###########################################################################
    def __generate_charts(self):
        graphs.setup()
        self.__generate_bod_1801_components_bar_chart()
        self.__generate_donut_charts()

    def __generate_bod_1801_components_bar_chart(self):
        bod_1801_bar = graphs.MyTrustyBar(
            percentage_list=[
                self.__uses_https_percentage,
                self.__enforces_https_percentage,
                self.__hsts_percentage,
                self.__has_no_weak_crypto_percentage
            ],
            label_list=[
                'Uses\nHTTPS',
                'Enforces\nHTTPS',
                'Uses Strong\nHSTS',
                'No SSLv2/v3,\n3DES,RC4'
            ],
            fill_color=graphs.DARK_BLUE,
            title='BOD 18-01 HTTPS Components')
        bod_1801_bar.plot(filename='bod-18-01-https-components')

    def __generate_donut_charts(self):
        bod_1801_donut = graphs.MyDonutPie(
            percentage_full=round(self.__bod_1801_percentage),
            label='BOD 18-01\nCompliant\n(Web)',
            fill_color=graphs.DARK_BLUE)
        bod_1801_donut.plot(filename='bod-18-01-compliant')

    ###########################################################################
    # Final Document Generation and Assembly
    ###########################################################################
    def __generate_mustache_json(self, filename):
        # result = {'all_domains':self.__all_domains}
        result = {'report_doc': self.__report_doc}
        result['ineligible_domains'] = self.__ineligible_domains
        result['domain_count'] = self.__domain_count
        result['subdomain_count'] = self.__subdomain_count
        result['base_domain_count'] = self.__base_domain_count
        result['all_eligible_domains_count'] = \
            self.__all_eligible_domains_count
        result['eligible_domains_count'] = self.__eligible_domains_count
        result['eligible_subdomains_count'] = self.__eligible_subdomains_count
        result['https_compliance_list'] = self.__https_compliance_list
        result['non_https_compliance_list'] = self.__non_https_compliance_list
        result['title_date_tex'] = \
            self.__generated_time.strftime('{%d}{%m}{%Y}')
        result['agency'] = self.__agency
        result['agency_id'] = self.__agency_id
        result['strictly_forces_percentage'] = round(
            self.__strictly_forces_count / self.__domain_count * 100.0,
            1
        )
        result['downgrades_percentage'] = round(
            self.__downgrades_count / self.__domain_count * 100.0,
            1
        )
        result['hsts_percentage'] = self.__hsts_percentage
        result['hsts_preloaded_percentage'] = round(
            self.__hsts_preloaded_count / self.__domain_count * 100.0,
            1
        )
        result['hsts_entire_domain_percentage'] = round(
            self.__hsts_entire_domain_count / self.__domain_count * 100.0,
            1
        )
        # result['strictly_forces_percentage'] = 0
        # result['downgrades_percentage'] = 0
        # result['hsts_preloaded_percentage'] = 0
        # result['hsts_entire_domain_percentage'] = 0
        result['domain_has_no_weak_crypto_count'] = \
            self.__domain_has_no_weak_crypto_count
        result['has_no_weak_crypto_percentage'] = \
            self.__has_no_weak_crypto_percentage
        result['bod_1801_percentage'] = self.__bod_1801_percentage
        result['bod_1801_count'] = self.__bod_1801_count
        result['domain_supports_https_count'] = \
            self.__domain_supports_https_count  # added
        result['uses_https_percentage'] = self.__uses_https_percentage
        result['enforces_https_percentage'] = self.__enforces_https_percentage
        result['strictly_forces_count'] = self.__strictly_forces_count
        result['domain_enforces_https_count'] = \
            self.__domain_enforces_https_count
        result['hsts_count'] = self.__hsts_count
        result['hsts_preloaded_count'] = self.__hsts_preloaded_count
        result['hsts_preload_ready_count'] = self.__hsts_preload_ready_count
        result['domain_uses_strong_hsts_count'] = \
            self.__domain_uses_strong_hsts_count
        result['https_expired_cert_count'] = self.__https_expired_cert_count
        result['https_bad_hostname_count'] = self.__https_bad_hostname_count
        result['https_bad_chain_count'] = self.__https_bad_chain_count
        result['hsts_low_max_age_count'] = self.__hsts_low_max_age_count

        self.__latex_escape_structure(result['report_doc'])

        with open(filename, 'w') as out:
            out.write(json.dumps(result))

    def __generate_latex(self, mustache_file, json_file, latex_file):
        template = codecs.open(mustache_file, 'r', encoding='utf-8').read()

        with codecs.open(json_file, 'r', encoding='utf-8') as data_file:
            data = json.load(data_file)

        r = pystache.render(template, data)
        with codecs.open(latex_file, 'w', encoding='utf-8') as output:
            output.write(r)

    def __generate_final_pdf(self):
        if self.__debug:
            output = sys.stdout
        else:
            output = open(os.devnull, 'w')

        return_code = subprocess.call(['xelatex', REPORT_TEX],
                                      stdout=output,
                                      stderr=subprocess.STDOUT)
        assert return_code == 0, \
            'xelatex pass 1 of 2 return code was %s' % return_code

        return_code = subprocess.call(['xelatex', REPORT_TEX],
                                      stdout=output,
                                      stderr=subprocess.STDOUT)
        assert return_code == 0, \
            'xelatex pass 2 of 2 return code was %s' % return_code


def main():
    args = docopt(__doc__, version='v0.0.1')
    db = db_from_config(DB_CONFIG_FILE)

    print("Generating HTTPS Report for {}...".format(args['"AGENCY"']))
    generator = ReportGenerator(db, args['"AGENCY"'], debug=args['--debug'])
    generator.generate_https_scan_report()
    print("Done")
    sys.exit(0)


if __name__ == '__main__':
    main()
