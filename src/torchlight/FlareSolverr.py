import aiohttp

FLARESOLVERR_URL = "http://127.0.0.1:8191/v1"

_session: aiohttp.ClientSession | None = None


def set_flaresolverr_url(url: str) -> None:
    global FLARESOLVERR_URL
    FLARESOLVERR_URL = url


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session


async def close_cf_session() -> None:
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None


async def get_cf_session(url: str, proxy: str | None = None) -> tuple[dict[str, str], str]:
    payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}

    # Pass proxy to FlareSolverr if specified
    if proxy:
        payload["proxy"] = {"url": proxy}

    session = _get_session()
    async with session.post(FLARESOLVERR_URL, json=payload, timeout=65) as response:
        res_data = await response.json()
        if res_data.get("status") == "ok":
            solution = res_data.get("solution", {})
            user_agent = solution.get("userAgent", "")
            cookies = {c["name"]: c["value"] for c in solution.get("cookies", [])}
            return cookies, user_agent
        else:
            raise RuntimeError(f"FlareSolverr error: {res_data.get('message')}")
