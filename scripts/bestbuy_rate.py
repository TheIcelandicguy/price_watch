import asyncio, sys
sys.path.insert(0, "/mnt/e/price_watch")
from curl_cffi.requests import AsyncSession

URL = "https://www.bestbuy.com/product/logitech-m310-wireless-optical-ambidextrous-mouse-wireless-peacock-blue/J7H7ZLVLQJ"


async def one(i):
    s = AsyncSession(impersonate="chrome131")
    try:
        r = await s.get(URL, timeout=30, allow_redirects=True)
        print(f"  #{i}: {r.status_code} len={len(r.text or '')}")
    except Exception as e:
        print(f"  #{i}: ERR {type(e).__name__}: {str(e)[:50]}")
    finally:
        await s.close()


async def main():
    for i in range(6):
        await one(i + 1)


asyncio.run(main())
