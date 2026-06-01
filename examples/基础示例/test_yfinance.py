import akshare_proxy_patch

akshare_proxy_patch.install_yfinance_patch(
    "101.201.173.125",
    auth_token="你的TOKEN",
    retry=30,
)


import yfinance as yf

data = yf.download("AAPL", start="2017-01-01", end="2017-04-30")

print(data)
