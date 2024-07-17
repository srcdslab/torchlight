#!/bin/bash

# CLI
if [ -z "${DATA_PATH}" ];
then
    export DATA_PATH="$PWD";
fi

if [ -z "${STARTUP}" ];
then
    export STARTUP="torchlight";
fi

cd "$DATA_PATH"

# Replace Startup Variables
MODIFIED_STARTUP=`eval echo $(echo ${STARTUP} | sed -e 's/{{/${/g' -e 's/}}/}/g')`
echo ":$DATA_PATH$ ${MODIFIED_STARTUP}"

# Run the Server
eval ${MODIFIED_STARTUP}
