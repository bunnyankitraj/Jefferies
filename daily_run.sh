#!/bin/bash
cd /Users/ankit/Developer/ALGO-TRADE/Jefferies
source .venv/bin/activate
python -m automation.job >> cron_log.txt 2>&1
