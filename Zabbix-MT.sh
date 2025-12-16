#!/bin/bash

# application home
src="${BASH_SOURCE[0]}"

if [ -L "$src" ]; then
    path="$(readlink "$src")"
else
    path="$0"
fi

home=$(cd $(dirname $path) && pwd)

if [ -d $home/venv ];
then
    . $home/venv/bin/activate
fi

cd $home

# run
python main.py "$@"
