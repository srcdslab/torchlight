#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import json
import sys

class Config():
	def __init__(self):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Config = dict()
		if len(sys.argv) >= 2:
			self.ConfigPath = sys.argv[1]
		else:
			self.ConfigPath = "config/config.json"
		self.Load()

	def Load(self):
		try:
			with open(self.ConfigPath, "r") as fp:
				self.Config = json.load(fp)
		except ValueError as e:
			self.Logger.error(sys._getframe().f_code.co_name + ' ' + str(e))
			return 1
		return 0

	def __getitem__(self, key):
		if key in self.Config:
			return self.Config[key]
		return None
