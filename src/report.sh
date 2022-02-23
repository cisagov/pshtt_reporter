#!/bin/bash

HOME_DIR='/home/cisa'
SHARED_DIR=$HOME_DIR'/shared'

# Prepare fonts
echo "Preparing fonts..."
cp ./fonts/* /usr/share/fonts/truetype/
fc-cache -f

echo 'Waiting for saver'
while [ "$(redis-cli -h redis get saving_complete)" != "true" ]; do
  sleep 5
done
echo Saver finished

# Don't delete saving_complete here since trustymail_reporter may be
# using it too.

# Because HHS/NASA reports are large, we need to increase buffer size (LaTeX)
sed -i 's/buf_size = 200000/buf_size = 1000000/' /usr/share/texmf/web2c/texmf.cnf

echo Creating reporting folders...
mkdir -p $SHARED_DIR/artifacts/reporting/pshtt_reports

# Grab OCSP/CRL hosts.  These hosts are to be removed from the list of
# hosts to be evaluated for HTTPS compliance, since they are not
# required to satisfy BOD 18-01.  For more information see here:
# https://https.cio.gov/guide/#are-federally-operated-certificate-revocation-services-crl-ocsp-also-required-to-move-to-https
wget https://raw.githubusercontent.com/cisagov/dotgov-data/main/dotgov-websites/ocsp-crl.csv \
  -O $SHARED_DIR/artifacts/ocsp-crl.csv

# Generate agency reports
cd $SHARED_DIR/artifacts/reporting/pshtt_reports || exit 1
$HOME_DIR/report/create_all_reports.py

# Wait for the trustworthy email reporting to finish
echo Waiting for trustworthy email reporting
while [ "$(redis-cli -h redis get trustymail_reporting_complete)" != "true" ]; do
  sleep 5
done
echo Trustworthy email reporting finished

# Archive artifacts folder
echo Archiving Results...
mkdir -p $SHARED_DIR/archive/
TODAY=$(date +'%Y-%m-%d')
mv $SHARED_DIR/artifacts $SHARED_DIR/artifacts_"$TODAY"
tar czf $SHARED_DIR/archive/artifacts_"$TODAY".tar.gz -C $SHARED_DIR artifacts_"$TODAY"/
# Save the artifacts directory as latest
rm -rf $SHARED_DIR/archive/latest
mv $SHARED_DIR/artifacts_"$TODAY" $SHARED_DIR/archive/latest

# No longer needed
redis-cli -h redis del saving_complete trustymail_reporting_complete

# This is the end of the line, so tell redis to shutdown
redis-cli -h redis shutdown
