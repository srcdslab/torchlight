#!/usr/bin/python3
# -*- coding: utf-8 -*-
import logging
import json
from collections import OrderedDict

class AccessManager():
	ACCESS_FILE = "config/access.json"
	def __init__(self):
		self.Logger = logging.getLogger(__class__.__name__)
		self.AccessDict = OrderedDict()

	def Load(self):
		self.Logger.info("Loading access from {0}".format(self.ACCESS_FILE))

		with open(self.ACCESS_FILE, "r") as fp:
			self.AccessDict = json.load(fp, object_pairs_hook = OrderedDict)

	def Save(self):
		self.Logger.info("Saving access to {0}".format(self.ACCESS_FILE))

		self.AccessDict = OrderedDict(
			sorted(self.AccessDict.items(), key = lambda x: x[1]["level"], reverse = True))

		with open(self.ACCESS_FILE, "w") as fp:
			json.dump(self.AccessDict, fp, indent = '\t')

	def __len__(self):
		return len(self.AccessDict)

	def __getitem__(self, key):
		if key in self.AccessDict:
			return self.AccessDict[key]

	def __setitem__(self, key, value):
		self.AccessDict[key] = value

	def __delitem__(self, key):
		if key in self.AccessDict:
			del self.AccessDict[key]

	def __iter__(self):
		return self.AccessDict.items().__iter__()
