#!/bin/bash
# example: ./get_traffic_info eth0

IF_NAME=$1

ethtool_res=$(ethtool -S "$IF_NAME")

#rx_q_num=$(echo "$ethtool_res" | grep 'rxq' | grep -c 'packets')
#tx_q_num=$(echo "$ethtool_res" | grep 'txq' | grep -c 'packets')

total_rx_packets=$(echo "$ethtool_res" | grep -o 'rx_packets: [0-9]*' | head -1 | awk '{print $2}')
total_tx_packets=$(echo "$ethtool_res" | grep -o 'tx_packets: [0-9]*' | head -1 | awk '{print $2}')
total_rx_bytes=$(echo "$ethtool_res" | grep -o 'rx_bytes: [0-9]*' | head -1 | awk '{print $2}')
total_tx_bytes=$(echo "$ethtool_res" | grep -o 'tx_bytes: [0-9]*' | head -1 | awk '{print $2}')
total_rx_errors=$(echo "$ethtool_res" | grep -o 'rx_errors: [0-9]*' | head -1 | awk '{print $2}')
total_tx_errors=$(echo "$ethtool_res" | grep -o 'tx_errors: [0-9]*' | head -1 | awk '{print $2}')
total_rx_dropped=$(echo "$ethtool_res" | grep -o 'rx_dropped: [0-9]*' | head -1 | awk '{print $2}')
total_tx_dropped=$(echo "$ethtool_res" | grep -o 'tx_dropped: [0-9]*' | head -1 | awk '{print $2}')

ip_res=$(ip -s -s -j link show dev "$IF_NAME")
ip_json="\"ip\":"$ip_res""

tc_res=$(tc -p -s -d -j qdisc show dev "$IF_NAME")
tc_json="\"tc\":"$tc_res""

ethtool_json="\"ethtool\":{ \"rx_packets\":\""$total_rx_packets"\",\"tx_packets\":\""$total_tx_packets"\", \
\"rx_bytes\":\""$total_rx_bytes"\",\"tx_bytes\":\""$total_tx_bytes"\", \
\"rx_errors\":\""$total_rx_errors"\",\"tx_errors\":\""$total_tx_errors"\", \
\"rx_dropped\":\""$total_rx_dropped"\",\"tx_dropped\":\""$total_tx_dropped"\" }"


num_rx_queues=$(find /sys/class/net/"$IF_NAME"/queues/rx-* -maxdepth 0 -type d | wc -l)
num_tx_queues=$(find /sys/class/net/"$IF_NAME"/queues/tx-* -maxdepth 0 -type d | wc -l)

num_queue_json="\"num_queue\":{\"num_rx_queues\":\""$num_rx_queues"\",\"num_tx_queues\":\""$num_tx_queues"\"}"

timestamp_json="\"timestamp\":"$(date +%s%N)""

netstat_res=$(netstat -s)
tmp=0
netstat_json="\"netstat\":{"
while IFS= read -r line; do
        json_line=""
        if [[ $line != "   "* ]]; then
                if [[ $tmp == 0 ]]; then
                        json_line="\"${line::-1}\":{"
                        tmp=1
                else
                        json_line="},\"${line::-1}\":{"
                fi
        else
                trimmed_line=$(echo "$line" | awk '{$1=$1;print}')
                if [[ $trimmed_line =~ ^[0-9] ]]; then
                        value=$(echo "$trimmed_line" | awk '{print $1}')
                        key="${trimmed_line:${#value}+1 }"
			key="${key// /_}"
			if [[ -z "${value// }"  ]];then
				value="-1"
			fi
                        json_line="\"$key\":$value,"
                else
                        IFS=: read -r key value <<< "$trimmed_line"
                        value="${value:1}"
			if [[ -z "${value// }"  ]];then
				value="-1"
			fi
                        json_line="\"$key\":$value,"
                fi
        fi
        netstat_json+=" $json_line"
done <<< "$netstat_res"
netstat_json+=" } }"


echo "{ $ip_json, $tc_json, $num_queue_json, $netstat_json, $timestamp_json }"
