import sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi import requests as cr

url = "https://www.amazon.de/-/en/gp/product/B0DTGNB9Q5/ref=ox_sc_act_title_1?smid=A3JWKAKR8XB7XF&th=1"

def classify(html):
    low = html.lower()
    if "weiter shoppen" in low or "continue shopping" in low or "klicke auf die schaltfläche" in low:
        return "INTERSTITIAL"
    if 'id="producttitle"' in low or "a-price-whole" in low:
        return "PRODUCT"
    return "OTHER(len=%d)" % len(html)

# A) fresh chrome session EACH request
print("=== A: fresh chrome session per request ===")
for i in range(4):
    s = cr.Session(impersonate="chrome")
    r = s.get(url, timeout=30)
    print(f"  req{i+1}: {classify(r.text)}")

# B) persistent chrome session but clear cookies before each
print("=== B: persistent chrome session, clear cookies each time ===")
s = cr.Session(impersonate="chrome")
for i in range(4):
    s.cookies.clear()
    r = s.get(url, timeout=30)
    print(f"  req{i+1}: {classify(r.text)}")

# C) one-shot cr.get (no session reuse) repeated
print("=== C: cr.get impersonate=chrome (no explicit session) x4 ===")
for i in range(4):
    r = cr.get(url, impersonate="chrome", timeout=30)
    print(f"  req{i+1}: {classify(r.text)}")
