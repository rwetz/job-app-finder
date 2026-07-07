import httpx

DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


def new_client(**kwargs) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=DEFAULT_TIMEOUT, **kwargs)
