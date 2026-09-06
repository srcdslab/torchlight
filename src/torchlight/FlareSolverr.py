import aiohttp

DEFAULT_FLARESOLVERR_URL = "http://127.0.0.1:8191/v1"


class FlareSolverr:
    def __init__(self, url: str = DEFAULT_FLARESOLVERR_URL) -> None:
        self.url = url
        self._session: aiohttp.ClientSession | None = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def get_cf_session(self, url: str, proxy: str | None = None) -> tuple[dict[str, str], str]:
        payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}

        # Pass proxy to FlareSolverr if specified
        if proxy:
            payload["proxy"] = {"url": proxy}

        session = self._get_session()
        async with session.post(self.url, json=payload, timeout=65) as response:
            res_data = await response.json()
            if res_data.get("status") == "ok":
                solution = res_data.get("solution", {})
                user_agent = solution.get("userAgent", "")
                cookies = {c["name"]: c["value"] for c in solution.get("cookies", [])}
                return cookies, user_agent
            else:
                raise RuntimeError(f"FlareSolverr error: {res_data.get('message')}")
