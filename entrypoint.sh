#!/bin/bash

DISPLAY=0
DONE="no"

while [ "$DONE" == "no" ]
do
   out=$(xdpyinfo -display :$DISPLAY 2>&1)
   if [[ "$out" == name* ]] || [[ "$out" == Invalid* ]]
   then
      # command succeeded; or failed with access error;  display exists
      (( DISPLAY+=1 ))
   else
      # display doesn't exist
      DONE="yes"
   fi
done

echo "Starting xvfb on screen $DISPLAY"

Xvfb :$DISPLAY -screen 0 1024x768x16 -nolisten tcp -nolisten unix &

export DISPLAY=:$DISPLAY

wine wineboot --init

python3.6 /home/torchlight/main.py
