import time
import random
import threading
import sys

# 1. 导入必要的库
try:
    from curl_cffi import requests as curl_requests
    from curl_cffi.requests import BrowserType
    from curl_cffi.requests.errors import RequestsError as RequestException
except ImportError:
    raise ImportError("请执行 pip install curl_cffi 来安装依赖")

import requests as std_requests

__version__ = "0.4.0"

# 授权接口固定使用标准 requests，避免干扰
_auth_session = std_requests.Session()

target_browsers = [
    b
    for b in BrowserType.__dict__.values()
    if isinstance(b, str) and (b.startswith("chrome") or b.startswith("edge"))
]


class AuthCache:
    def __init__(self):
        self.data = None
        self.expire_at = 0
        self.lock = threading.Lock()
        self.ttl = 28


_cache = AuthCache()


def get_auth_config_with_cache(auth_url, auth_token):
    now = time.time()
    if _cache.data and now < _cache.expire_at:
        return _cache.data
    with _cache.lock:
        if _cache.data and now < _cache.expire_at:
            return _cache.data
        try:
            resp = _auth_session.get(
                auth_url,
                params={"token": auth_token, "version": __version__},
                timeout=(1.5, 3),
            )
            data = resp.json()
            if data.get("ua"):
                _cache.data = data
                _cache.expire_at = now + _cache.ttl
                return data
            print(f"授权失败: {data.get('error_msg')}")
        except:
            pass
        return _cache.data


default_hook_domains = [
    "fund.eastmoney.com",
    "push2.eastmoney.com",
    "push2his.eastmoney.com",
    "emweb.securities.eastmoney.com",
]


def install_patch(
    auth_ip, auth_token="", retry=30, hook_domains=default_hook_domains, timeout=5
):
    # 获取原始的 curl_cffi Session 类
    # 1. 解决 Linux 下的 AttributeError: 'curl_cffi.requests' has no attribute 'adapters'
    # 动态将标准 requests 的子模块挂载到 curl_requests 上
    needed_submodules = [
        "adapters",
        "auth",
        "cookies",
        "exceptions",
        "models",
        "status_codes",
        "structures",
        "utils",
        "packages",
    ]

    setattr(curl_requests, "RequestException", RequestException)
    for sub in needed_submodules:
        if not hasattr(curl_requests, sub):
            # 优先从标准 requests 借用这些定义，保证 akshare 里的 isinstance 或常量检查能过
            setattr(curl_requests, sub, getattr(std_requests, sub, None))

    _BaseSession = curl_requests.Session

    # 定义兼容 Windows 调用的子类
    class PatchedSession(_BaseSession):
        def mount(self, prefix, adapter):
            pass

        def request(self, method, url, **kwargs):
            is_target = any(d in (url or "") for d in hook_domains)
            clean_url = (url or "").split("?")[0].lower()
            if (
                not is_target
                or clean_url.endswith(".js")
                or clean_url.endswith(".html")
            ):
                return super().request(method, url, **kwargs)

            auth_url = f"http://{auth_ip}:47001/api/akshare-auth"

            for i in range(retry):
                auth_res = get_auth_config_with_cache(auth_url, auth_token)
                if not auth_res:
                    time.sleep(0.05)
                    continue

                # 适配参数
                headers = kwargs.get("headers") or {}
                headers["User-Agent"] = auth_res["ua"]
                kwargs["headers"] = headers
                kwargs["proxies"] = {
                    "http": auth_res["proxy"],
                    "https": auth_res["proxy"],
                }
                kwargs["timeout"] = timeout

                kwargs["impersonate"] = random.choice(target_browsers)
                # print(auth_res["proxy"], i, "=============")

                try:
                    # 关键：调用 curl_cffi 的原生 C 实现
                    resp = super().request(method, url, **kwargs)
                    if resp.status_code == 200:
                        # 业务逻辑验证...
                        return resp
                    with _cache.lock:
                        _cache.expire_at = 0
                except:
                    with _cache.lock:
                        _cache.expire_at = 0
                time.sleep(0.05)

            return super().request(method, url, **kwargs)

    # --- 核心改造：针对 Windows 的原地注入 ---

    # 定义顶层包装函数
    def patched_get(url, params=None, **kwargs):
        with PatchedSession() as s:
            return s.get(url, params=params, **kwargs)

    def patched_post(url, data=None, json=None, **kwargs):
        with PatchedSession() as s:
            return s.post(url, data=data, json=json, **kwargs)

    # 1. 替换 curl_requests 的成员
    curl_requests.Session = PatchedSession
    curl_requests.get = patched_get
    curl_requests.post = patched_post

    # 2. 【核心】原地修改 sys.modules 中的 requests 对象
    # 即使 akshare 已经加载了 requests，我们直接修改 requests 模块的内容
    if "requests" in sys.modules:
        req_mod = sys.modules["requests"]
        req_mod.Session = PatchedSession
        req_mod.get = patched_get
        req_mod.post = patched_post
        req_mod.request = patched_get  # 部分库直接调 request

    # 3. 确保后续导入重定向
    sys.modules["requests"] = curl_requests


def install_yfinance_patch(
    auth_ip, auth_token="", retry=30, hook_domains=["finance.yahoo.com"]
):
    from .yfinance import install_yfinance_patch_main

    install_yfinance_patch_main(auth_ip, auth_token, retry, hook_domains)
