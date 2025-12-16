#!/bin/bash

app="Zabbix-MT"

# application home
src="${BASH_SOURCE[0]}"

if [ -L "$src" ]; then
    path="$(readlink "$src")"
else
    path="$0"
fi

home=$(cd $(dirname $path) && pwd)

exscript="$home/../$app.sh"

if [ -f "$exscript" ] || [ -L "$exscript" ]; then
    rm -f "$exscript"
fi

ln -s $home/$app.sh $exscript

chown -R zabbix:zabbix $home/../$app*
