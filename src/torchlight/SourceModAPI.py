import functools
from typing import Any

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
    ) -> dict[str, Any]:
        json_obj = {"method": "function", "function": function, "args": args}

        res_raw = await self.async_client.Send(json_obj)

        res: dict[str, Any] = {}
        if isinstance(res_raw, dict):
            res = res_raw

        if res["error"]:
            raise Exception("{}({})\n{}".format(function, args, res["error"]))

        return res
