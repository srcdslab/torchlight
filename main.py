#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import asyncio
import os
import sys
import threading
import traceback
import gc
from importlib import reload

global TorchMaster

import Torchlight.Torchlight
from Torchlight.SourceRCONServer import SourceRCONServer

if __name__ == '__main__':
	logging.basicConfig(level = logging.DEBUG)

	Loop = asyncio.get_event_loop()

	global TorchMaster
	TorchMaster = Torchlight.Torchlight.TorchlightHandler(Loop)

	# Handles new connections on 0.0.0.0:27015
	RCONConfig = TorchMaster.Config["TorchRCON"]
	RCONServer = SourceRCONServer(Loop, TorchMaster,
		Host = RCONConfig["Host"],
		Port = RCONConfig["Port"],
		Password = RCONConfig["Password"])

	# Run!
	Loop.run_forever()
