import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def get(path, token=None):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def post(path, body, token=None):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def test_endpoints():
    print(f"Testing live server at {BASE_URL}...")
    
    # 1. Health check
    status, body = get("/api/health")
    print(f"1. /api/health: {status} - {body}")
    assert status == 200

    # 2. Login page HTML
    status, body = get("/login")
    print(f"2. /login: {status} (HTML length: {len(body)})")
    assert status == 200

    # 3. Explore Projects
    status, body = get("/api/projects")
    projects = json.loads(body)
    print(f"3. /api/projects: {status} (Projects found: {len(projects)})")
    assert status == 200
    assert len(projects) > 0

    # 4. Bazaar Hardware Items
    status, body = get("/api/bazaar/items")
    items = json.loads(body)
    print(f"4. /api/bazaar/items: {status} (Items found: {len(items)})")
    assert status == 200
    assert len(items) > 0

    # 5. Protected Dashboard (Unauthenticated -> 401)
    status, body = get("/api/dashboard/overview")
    print(f"5. /api/dashboard/overview (unauthenticated): {status}")
    assert status == 401

    # 6. Demo Persona Login (Student)
    status, body = post("/api/auth/demo-login", {"user_id": "usr_student_1"})
    print(f"6. /api/auth/demo-login: {status}")
    assert status == 200
    data = json.loads(body)
    token = data["session_token"]
    assert token

    # 7. Protected Dashboard (Authenticated -> 200)
    status, body = get("/api/dashboard/overview", token=token)
    dash_data = json.loads(body)
    print(f"7. /api/dashboard/overview (authenticated): {status} - Metrics: {dash_data.get('metrics')}")
    assert status == 200

    # 8. Forgot Password Flow
    status, body = post("/api/auth/forgot-password", {"email": "aarav.sharma@cse.iitb.ac.in"})
    print(f"8. /api/auth/forgot-password: {status}")
    assert status in [200, 429]
    if status == 200:
        forgot_data = json.loads(body)
        reset_token = forgot_data.get("reset_token")
        assert forgot_data.get("success") is True

        # 9. Reset Password Flow
        if reset_token:
            status, body = post("/api/auth/reset-password", {"token": reset_token, "newPassword": "Password123!"})
            print(f"9. /api/auth/reset-password: {status}")
            assert status == 200
            reset_data = json.loads(body)
            assert reset_data.get("success") is True
    else:
        print("   (Rate limiting active - protected)")

    # 10. Send OTP Flow
    import time
    otp_email = f"live.tester_{int(time.time() * 1000)}@gmail.com"
    status, body = post("/api/auth/send-otp", {"email": otp_email})
    print(f"10. /api/auth/send-otp: {status}")
    assert status in [200, 429]
    if status == 200:
        otp_data = json.loads(body)
        assert otp_data.get("success") is True
        live_otp = otp_data.get("otp")

        # 11. Verify OTP Flow
        if live_otp:
            status, body = post("/api/auth/verify-otp", {"email": otp_email, "otp": live_otp})
            print(f"11. /api/auth/verify-otp: {status}")
            assert status == 200
            verify_data = json.loads(body)
            assert verify_data.get("verified") is True
    else:
        print("   (OTP rate limiting active - IP protected)")

    # 12. Project Store Items (Software)
    status, body = get("/api/project-store/items")
    print(f"12. /api/project-store/items: {status}")
    assert status == 200
    soft_items = json.loads(body)
    print(f"    Found {len(soft_items)} software items.")
    assert len(soft_items) > 0

    # 13. Hardware Store Items (Hardware)
    status, body = get("/api/hardware-store/items")
    print(f"13. /api/hardware-store/items: {status}")
    assert status == 200
    hard_items = json.loads(body)
    print(f"    Found {len(hard_items)} hardware items.")
    assert len(hard_items) > 0

    print("\n>>> ALL LIVE SERVER ENDPOINTS VERIFIED & OPERATIONAL! <<<")

if __name__ == "__main__":
    test_endpoints()
