import requests

FLARESOLVERR_URL = "http://0.0.0.0:8191/v1"

def set_flaresolverr_url(url: str) -> None:
    global FLARESOLVERR_URL
    FLARESOLVERR_URL = url


def get_flaresolverr_session(url: str) -> tuple[str, str] | str | None:
    payload = {
        "cmd": "request.get",
        "url": url,
        "maxTimeout": 60000,
    }

    try:
        response = requests.post(FLARESOLVERR_URL, json=payload, timeout=65)
        res_data = response.json()
        
        if res_data.get("status") == "ok":
            solution = res_data.get("solution", {})
            user_agent = solution.get("userAgent", "")
            
            # Convert list of cookie objects into standard HTTP Cookie header format
            cookies = solution.get("cookies", [])
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            return cookie_str, user_agent
    except Exception as e:
        return f"Failed to get FlareSolverr session: {e}"

    return None
