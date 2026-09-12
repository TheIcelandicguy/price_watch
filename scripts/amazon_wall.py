import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr

url = "https://www.amazon.de/-/en/gp/product/B0DTGNB9Q5/ref=ox_sc_act_title_1?smid=A3JWKAKR8XB7XF&th=1"

def classify(html):
    low = html.lower()
    if "weiter shoppen" in low or "continue shopping" in low or "klicke auf die schaltfläche" in low:
        return "INTERSTITIAL(continue-shopping)"
    if "enter the characters you see below" in low or "/errors/validatecaptcha" in low:
        return "CAPTCHA"
    if 'id="producttitle"' in low or "a-price-whole" in low:
        return "PRODUCT"
    return "OTHER(len=%d)" % len(html)

# 1) No impersonation, minimal headers -> try to provoke the wall
print("=== bare session (no impersonate) ===")
s = cr.Session()
for i in range(3):
    try:
        r = s.get(url, timeout=30)
        print(f"  try{i+1}: status={r.status_code} -> {classify(r.text)} cookies={len(s.cookies)}")
    except Exception as e:
        print(f"  try{i+1}: ERR {e}")

# 2) chrome impersonation, retry within same session
print("=== chrome session, 3 tries same session ===")
s2 = cr.Session(impersonate="chrome")
for i in range(3):
    try:
        r = s2.get(url, timeout=30)
        print(f"  try{i+1}: status={r.status_code} -> {classify(r.text)} cookies={len(s2.cookies)}")
    except Exception as e:
        print(f"  try{i+1}: ERR {e}")
