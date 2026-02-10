import httpx
import json
import asyncio
from nanobot.api.main import app

async def test_endpoints_direct():
    endpoints = [
        "/api/status",
        "/api/config/skills",
        "/api/auth/github/status"
    ]
    
    results = []
    
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        for url in endpoints:
            print(f"Testing {url}...")
            try:
                response = await client.get(url)
                status_ok = response.status_code == 200
                content = response.json()
                
                # Check for "TODO" or placeholder info
                content_str = json.dumps(content, ensure_ascii=False)
                has_placeholder = "TODO" in content_str or "未实现" in content_str
                
                results.append({
                    "url": url,
                    "status_code": response.status_code,
                    "status_ok": status_ok,
                    "content": content,
                    "has_placeholder": has_placeholder
                })
            except Exception as e:
                results.append({
                    "url": url,
                    "error": str(e),
                    "status_ok": False
                })

    for res in results:
        print("-" * 20)
        print(f"URL: {res['url']}")
        if "error" in res:
            print(f"Error: {res['error']}")
        else:
            print(f"HTTP Status: {res['status_code']} ({'PASS' if res['status_ok'] else 'FAIL'})")
            print(f"Content: {json.dumps(res['content'], indent=2, ensure_ascii=False)}")
            print(f"No Placeholder Check: {'PASS' if not res['has_placeholder'] else 'FAIL (Contains placeholder)'}")

if __name__ == "__main__":
    asyncio.run(test_endpoints_direct())
