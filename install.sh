#!/bin/bash

# application home
src="${BASH_SOURCE[0]}"

if [ -L "$src" ]; then
    path="$(readlink "$src")"
else
    path="$0"
fi

home=$(cd $(dirname $path) && pwd)

ln -s $home/zabbix-MT.sh $home/../zabbix-MT.sh

chown -R zabbix:zabbix $home/../zabbix-MT*
