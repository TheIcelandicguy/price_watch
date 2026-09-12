import asyncio, sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi.requests import AsyncSession
from custom_components.price_watch.extractor import try_jsonld

URL = "https://www.bestbuy.com/product/logitech-m310-wireless-optical-ambidextrous-mouse-wireless-peacock-blue/J7H7ZLVLQJ"
ARGOS = "https://www.argos.co.uk/product/9420399"


async def attempt(label, url, http_version=None):
    kw = {"impersonate": "chrome131"}
    s = AsyncSession(**kw)
    try:
        g = {"timeout": 30, "allow_redirects": True}
        if http_version is not None:
            g["http_version"] = http_version
        r = await s.get(url, **g)
        ld = try_jsonld(r.text or "")
        print(f"  {label:32} -> {r.status_code} len={len(r.text or '')} price={(ld or {}).get('price')}")
    except Exception as e:
        print(f"  {label:32} -> ERR {type(e).__name__}: {str(e)[:55]}")
    finally:
        await s.close()


async def main():
    from curl_cffi.const import CurlHttpVersion
    print("BESTBUY:")
    await attempt("async fresh (default h2)", URL)
    await attempt("async fresh http1.1", URL, CurlHttpVersion.V1_1)
    print("ARGOS (3 sequential fresh sessions):")
    for i in range(3):
        await attempt(f"fresh #{i+1}", ARGOS)

asyncio.run(main())
