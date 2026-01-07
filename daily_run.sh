#!/bin/bash
cd /Users/ankit/Developer/ALGO-TRADE/Jefferies
source .venv/bin/activate
python automation/job.py >> cron_log.txt 2>&1
