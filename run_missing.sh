#!/usr/bin/env bash


python edgedroid.py -n 10 -p 0 -d 1h -t square00 --truncate 45 -m empirical -m theoretical -m naive -s adaptive-aperiodic --env EDGEDROID_ADAPTIVE_SAMPLING_DELAY_COST_WINDOW=10 -r 5 --noconfirm AperiodicWin10;

for dname in /opt/expeca/experiments/AperiodicWin10/*adaptive-aperiodic*; do
  sudo mv "$dname" "${dname//adaptive-aperiodic/adaptive-aperiodic-win10}";
done

python edgedroid.py -n 10 -p 0 -d 1h -t square00 --truncate 45 -m theoretical -m empirical -m naive -s regular-1.875 -r 5 --noconfirm Regular1875;
