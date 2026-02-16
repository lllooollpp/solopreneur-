import httpx
import json
import time

def test_endpoints():
    endpoints = [
        "http://127.0.0.1:8000/api/status",
        "http://127.0.0.1:8000/api/config/skills",
        "http://127.0.0.1:8000/api/auth/github/status"
    ]
    
    # Wait a bit for server to be fully ready
    time.sleep(2)
    
    results = []
    
    with httpx.Client() as client:
        for url in endpoints:
            print(f"Testing {url}...")
            try:
                response = client.get(url, timeout=5.0)
                status_ok = response.status_code == 200
                content = response.json()
                
                # Check for "TODO" or placeholder info
                content_str = json.dumps(content, ensure_ascii=False)
                has_placeholder = "TODO" in content_str or "未实�? in content_str
                
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
    test_endpoints()
