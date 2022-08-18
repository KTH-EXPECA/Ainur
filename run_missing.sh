#!/usr/bin/env bash

#>>>     data/runs_aug18/neuro-0.5_model-empirical_sampling-zero-wait_task-square00-45/clients-10/run-2/loop7
#>>>     data/runs_aug18/neuro-0.5_model-theoretical_sampling-regular-1.75_task-square00-45/clients-10/run-4/loop6
#>>>     data/runs_aug18/neuro-0.5_model-theoretical_sampling-regular-2.0_task-square00-45/clients-10/run-2/loop8
#>>>     data/runs_aug18/neuro-0.5_model-naive_sampling-regular-1.75_task-square00-45/clients-10/run-4/loop7
#>>>     data/runs_aug18/neuro-0.5_model-empirical_sampling-adaptive-aperiodic_task-square00-45/clients-10/run-5/loop8


python edgedroid.py -n 10 -p -d 1h -t square00 --truncate 45 -m empirical -s zero-wait -r 1 --noconfirm EmpiricalZeroWait;
python edgedroid.py -n 10 -p -d 1h -t square00 --truncate 45 -m theoretical -s regular-1.75 -r 1 --noconfirm TheoreticalRegular175;
python edgedroid.py -n 10 -p -d 1h -t square00 --truncate 45 -m theoretical -s regular-2.0 -r 1 --noconfirm TheoreticalRegular20;
python edgedroid.py -n 10 -p -d 1h -t square00 --truncate 45 -m naive -s regular-1.75 -r 1 --noconfirm NaiveRegular175;
python edgedroid.py -n 10 -p -d 1h -t square00 --truncate 45 -m empirical -s adaptive-aperiodic -r 1 --noconfirm EmpiricalAperiodic;