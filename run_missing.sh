#!/usr/bin/env bash

#>>>     data/runs_aug18/neuro-0.5_model-empirical_sampling-adaptive-aperiodic-win5_task-square00-45/clients-10/run-1/loop5
#>>>     data/runs_aug18/neuro-0.5_model-theoretical_sampling-regular-2.25_task-square00-45/clients-10/run-2/loop4


python edgedroid.py -n 10 -p 0 -d 1h -t square00 --truncate 45 -m empirical -s adaptive-aperiodic --env EDGEDROID_ADAPTIVE_SAMPLING_DELAY_COST_WINDOW=5 -r 1 --noconfirm EmpiricalAperiodicWin5;
python edgedroid.py -n 10 -p 0 -d 1h -t square00 --truncate 45 -m theoretical -s regular-2.25 --env EDGEDROID_ADAPTIVE_SAMPLING_DELAY_COST_WINDOW=5 -r 1 --noconfirm TheoreticalRegular225;
