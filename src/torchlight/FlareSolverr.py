import logging

import requests

FLARESOLVERR_URL = "http://127.0.0.1:8191/v1"

def set_flaresolverr_url(url: str) -> None:
    global FLARESOLVERR_URL
    FLARESOLVERR_URL = url


def get_flaresolverr_session(url: str, target_url, logger: logging.Logger) -> tuple[str, str] | None:
    payload = {
        "cmd": "request.get",
        "url": target_url,
        "maxTimeout": 60000,
    }

    try:
        response = requests.post(FLARESOLVERR_URL, json=payload, timeout=65)
        res_data = response.json()

        if res_data.get("status") == "ok":
            solution = res_data.get("solution", {})
            user_agent = solution.get("userAgent", "")

            cookies = solution.get("cookies", [])
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies if "name" in c and "value" in c])

            if not cookie_str:
                logger.warning(f"FlareSolverr returned 200 OK but no cookies for {target_url}")

            return (cookie_str, user_agent)

        logger.error(f"FlareSolverr error: {res_data.get('message')}")
    except Exception as e:
        logger.error(f"FlareSolverr request failed: {e}")

    return None
