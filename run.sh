#!/bin/bash
nohup venv/bin/python main.py > data/backtest.log 2>&1 &
echo $! > data/backtest.pid
