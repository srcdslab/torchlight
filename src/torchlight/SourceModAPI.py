#!/usr/bin/python3
# -*- coding: utf-8 -*-
import functools
from typing import Any, Dict

from torchlight.AsyncClient import AsyncClient


class SourceModAPI:
    def __init__(self, async_client: AsyncClient) -> None:
        self.async_client = async_client

    def __getattr__(self, attr: str) -> Any:
        # try:
        #     return super(SourceModAPI, self).__getattr__(attr)
        # except AttributeError:
        return functools.partial(self._MakeCall, attr)

    async def _MakeCall(
        self, function: str, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        Obj = {"method": "function", "function": function, "args": args}

        ResRaw = await self.async_client.Send(Obj)

        Res: Dict[str, Any] = dict()
        if isinstance(ResRaw, Dict):
            Res = ResRaw

        if Res["error"]:
            raise Exception("{0}({1})\n{2}".format(function, args, Res["error"]))

        return Res
