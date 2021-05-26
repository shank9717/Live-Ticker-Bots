#!/bin/sh
pid=`ps aux | grep "python3 __main__.py" | awk '{ print $2 }' | xargs pwdx | grep -F -- " $(cd ../ && pwd)" | awk '{print $1}'| sed s/.$//`
kill -9 $pid