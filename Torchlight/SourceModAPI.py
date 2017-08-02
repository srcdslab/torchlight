#!/usr/bin/python3
# -*- coding: utf-8 -*-
import functools

class SourceModAPI:
	def __init__(self, master):
		self.Torchlight = master

	def __getattr__(self, attr):
		try:
			return super(SourceModAPI, self).__getattr__(attr)
		except AttributeError:
			return functools.partial(self._MakeCall, attr)

	async def _MakeCall(self, function, *args, **kwargs):
		Obj = {
			"method": "function",
			"function": function,
			"args": args
		}

		Res = await self.Torchlight().Send(Obj)

		if Res["error"]:
			raise Exception("{0}({1})\n{2}".format(function, args, Res["error"]))

		return Res
