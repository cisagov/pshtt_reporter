#!/bin/bash

HOME_DIR='/home/reporter'
SHARED_DIR=$HOME_DIR'/shared'

# Prepare fonts
echo "Preparing fonts..."
cp ./fonts/* /usr/share/fonts/truetype/
fc-cache -f

echo 'Waiting for saver'
while [ "$(redis-cli -h orchestrator_redis_1 get saving_complete)" != "true" ]
do
    sleep 5
done
echo "Saver finished"

# Don't delete saving_complete here since trustymail_reporter may be
# using it too.

# Because HHS/NASA reports are large, we need to increase buffer size (LaTeX)
sed -i 's/buf_size = 200000/buf_size = 1000000/' /usr/share/texmf/web2c/texmf.cnf

echo "Creating reporting folders..."
mkdir -p $SHARED_DIR/artifacts/reporting/pshtt_reports

# Generate agency reports
cd $SHARED_DIR/artifacts/reporting/pshtt_reports
$HOME_DIR/report/create_all_reports.py

# Wait for the trustworthy email reporting to finish
echo 'Waiting for trustworthy email reporting'
while [ "$(redis-cli -h orchestrator_redis_1 get trustymail_reporting_complete)" != "true" ]
do
    sleep 5
done
echo "Trustworthy email reporting finished"

# Archive artifacts folder
echo 'Archiving Results...'
mkdir -p $SHARED_DIR/archive/
TODAY=$(date +'%Y-%m-%d')
mv $SHARED_DIR/artifacts $SHARED_DIR/artifacts_$TODAY
tar czf $SHARED_DIR/archive/artifacts_$TODAY.tar.gz -C $SHARED_DIR artifacts_$TODAY/
# Save the artifacts directory as latest
rm -rf $SHARED_DIR/archive/latest
mv $SHARED_DIR/artifacts_$TODAY $SHARED_DIR/archive/latest

# No longer needed
redis-cli -h orchestrator_redis_1 del saving_complete trustymail_reporting_complete

# This is the end of the line, so tell redis to shutdown
redis-cli -h orchestrator_redis_1 shutdown
