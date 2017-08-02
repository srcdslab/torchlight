#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import json

class Config():
	def __init__(self):
		self.Logger = logging.getLogger(__class__.__name__)
		self.Config = dict()
		self.Load()

	def Load(self):
		try:
			with open("config.json", "r") as fp:
				self.Config = json.load(fp)
		except ValueError as e:
			self.Logger.error(sys._getframe().f_code.co_name + ' ' + str(e))
			return 1
		return 0

	def __getitem__(self, key):
		if key in self.Config:
			return self.Config[key]
		return None
