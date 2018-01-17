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

# No longer needed
redis-cli -h orchestrator_redis_1 del saving_complete

echo "Creating reporting folder..."
mkdir -p $SHARED_DIR/artifacts/reporting

# Because HHS/NASA reports are large, we need to increase buffer size (LaTeX)
sed -i 's/buf_size = 200000/buf_size = 400000/' /usr/share/texmf/web2c/texmf.cnf

mkdir -p $SHARED_DIR/artifacts/reporting/pshtt_reports
mkdir -p $SHARED_DIR/artifacts/reporting/pshtt_non-cyhy_reports

# Generate agency reports
cd $SHARED_DIR/artifacts/reporting/pshtt_reports
$HOME_DIR/report/create_all_reports.py

# Archive artifacts folder
echo 'Archiving Results...'
mkdir -p $SHARED_DIR/archive/
cd $SHARED_DIR
TODAY=$(date +'%Y-%m-%d')
mv artifacts artifacts_$TODAY
tar -czf $SHARED_DIR/archive/artifacts_$TODAY.tar.gz artifacts_$TODAY/

# Clean up
echo 'Cleaning up'
rm -rf artifacts_$TODAY

# Let redis know we're done
# redis-cli -h orchestrator_redis_1 set trustymail_reporting_complete true
# This is the end of the line, so tell redis to shutdown
redis-cli -h orchestrator_redis_1 shutdown
