import requests
import random
import time

BASE_URL = "YOUR_WEBSITE_URL"

# Valid credentials from your Flask app
VALID_USERS = [
    {"username": "admin", "password": "password123"},
    {"username": "user1", "password": "user1234"}
]

# Wrong credentials for attack simulation
INVALID_CREDENTIALS = [
    {"username": "admin", "password": "123456"},
    {"username": "admin", "password": "wrongpass"},
    {"username": "user1", "password": "qwerty"},
    {"username": "test", "password": "test123"},
    {"username": "guest", "password": "guest123"},
    {"username": "root", "password": "toor"},
]

# Routes
NORMAL_ROUTES = ["/", "/dashboard", "/activity", "/settings", "/logout"]
SUSPICIOUS_ROUTES = ["/admin", "/secret", "/unknownpage", "/activity", "/dashboard"]
ANOMALY_ROUTES = ["/admin", "/secret", "/report", "/wp-login", "/fake-api", "/doesnotexist"]
MIXED_EXTRA_ROUTES = ["/health", "/api/data"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DummyTrafficGenerator/1.0"
}


def print_response(method, route, status_code):
    print(f"[{method}] {route} -> Status: {status_code}")


def safe_get(session, route):
    try:
        response = session.get(BASE_URL + route, headers=HEADERS, timeout=10, allow_redirects=True)
        print_response("GET", route, response.status_code)
        return response
    except Exception as e:
        print(f"[ERROR] GET {route} failed: {e}")


def safe_post_login(session, username, password):
    try:
        response = session.post(
            BASE_URL + "/login",
            headers=HEADERS,
            data={"username": username, "password": password},
            timeout=10,
            allow_redirects=True
        )
        print_response("POST", f"/login ({username})", response.status_code)
        return response
    except Exception as e:
        print(f"[ERROR] POST /login failed for {username}: {e}")


def delay(min_s, max_s):
    time.sleep(random.uniform(min_s, max_s))


# -----------------------------
# MODE 1: NORMAL TRAFFIC
# -----------------------------
def generate_normal_traffic():
    print("\n=== GENERATING NORMAL TRAFFIC ===")
    session = requests.Session()

    # Fixed total requests ≈ 15
    safe_get(session, "/")
    delay(2, 4)

    safe_get(session, "/login")
    delay(2, 4)

    # 1 successful login
    creds = random.choice(VALID_USERS)
    safe_post_login(session, creds["username"], creds["password"])
    delay(2, 4)

    # Normal browsing
    for route in random.sample(NORMAL_ROUTES, len(NORMAL_ROUTES)):
        safe_get(session, route)
        delay(2, 4)

    # Some extra normal browsing
    for _ in range(8):
        route = random.choice(["/", "/dashboard", "/activity", "/settings"])
        safe_get(session, route)
        delay(2, 4)

    print("=== NORMAL TRAFFIC COMPLETED ===\n")


# -----------------------------
# MODE 2: SUSPICIOUS TRAFFIC
# -----------------------------
def generate_suspicious_traffic():
    print("\n=== GENERATING SUSPICIOUS TRAFFIC ===")
    session = requests.Session()

    # Fixed total requests ≈ 30
    safe_get(session, "/login")
    delay(1, 2)

    # 3 failed logins
    for _ in range(3):
        creds = random.choice(INVALID_CREDENTIALS)
        safe_post_login(session, creds["username"], creds["password"])
        delay(1, 2)

    # 1 successful login
    creds = random.choice(VALID_USERS)
    safe_post_login(session, creds["username"], creds["password"])
    delay(1, 2)

    # Suspicious probing
    suspicious_sequence = [
        "/admin", "/secret", "/unknownpage", "/activity", "/dashboard"
    ]

    for route in suspicious_sequence:
        safe_get(session, route)
        delay(1, 2)

    # Additional mixed suspicious browsing
    for _ in range(20):
        route = random.choice(["/login", "/admin", "/secret", "/unknownpage", "/activity", "/dashboard"])
        if route == "/login":
            safe_get(session, route)
        else:
            safe_get(session, route)
        delay(1, 2)

    print("=== SUSPICIOUS TRAFFIC COMPLETED ===\n")


# -----------------------------
# MODE 3: BRUTE FORCE / ANOMALY
# -----------------------------
def generate_anomaly_traffic():
    print("\n=== GENERATING BRUTE-FORCE / ANOMALY TRAFFIC ===")
    session = requests.Session()

    # Fixed total requests ≈ 100

    # Heavy failed login burst
    for _ in range(30):
        creds = random.choice(INVALID_CREDENTIALS)
        safe_post_login(session, creds["username"], creds["password"])
        delay(0.2, 0.5)

    # Repeated attack/recon routes
    for _ in range(70):
        route = random.choice(ANOMALY_ROUTES + ["/login"])
        if route == "/login":
            creds = random.choice(INVALID_CREDENTIALS)
            safe_post_login(session, creds["username"], creds["password"])
        else:
            safe_get(session, route)
        delay(0.2, 0.5)

    print("=== BRUTE-FORCE / ANOMALY TRAFFIC COMPLETED ===\n")


# -----------------------------
# MODE 4: MIXED TRAFFIC (BEST)
# -----------------------------
def generate_mixed_traffic():
    print("\n=== GENERATING MIXED TRAFFIC ===")

    # 30 normal-style requests
    print("\n--- Phase 1: Normal-like Traffic ---")
    session_normal = requests.Session()

    safe_get(session_normal, "/")
    delay(2, 4)

    safe_get(session_normal, "/login")
    delay(2, 4)

    creds = random.choice(VALID_USERS)
    safe_post_login(session_normal, creds["username"], creds["password"])
    delay(2, 4)

    for _ in range(27):
        route = random.choice(["/", "/dashboard", "/activity", "/settings", "/logout"])
        safe_get(session_normal, route)
        delay(2, 4)

    # 30 suspicious-style requests
    print("\n--- Phase 2: Suspicious Traffic ---")
    session_suspicious = requests.Session()

    for _ in range(3):
        creds = random.choice(INVALID_CREDENTIALS)
        safe_post_login(session_suspicious, creds["username"], creds["password"])
        delay(1, 2)

    creds = random.choice(VALID_USERS)
    safe_post_login(session_suspicious, creds["username"], creds["password"])
    delay(1, 2)

    for _ in range(26):
        route = random.choice(["/login", "/admin", "/secret", "/unknownpage", "/dashboard", "/activity"])
        if route == "/login":
            safe_get(session_suspicious, route)
        else:
            safe_get(session_suspicious, route)
        delay(1, 2)

    # 60 anomaly-style requests
    print("\n--- Phase 3: Anomaly Traffic ---")
    session_attack = requests.Session()

    for _ in range(15):
        creds = random.choice(INVALID_CREDENTIALS)
        safe_post_login(session_attack, creds["username"], creds["password"])
        delay(0.2, 0.5)

    for _ in range(45):
        route = random.choice(ANOMALY_ROUTES + MIXED_EXTRA_ROUTES + ["/login"])
        if route == "/login":
            creds = random.choice(INVALID_CREDENTIALS)
            safe_post_login(session_attack, creds["username"], creds["password"])
        else:
            safe_get(session_attack, route)
        delay(0.2, 0.5)

    print("=== MIXED TRAFFIC COMPLETED ===\n")


# -----------------------------
# MAIN MENU
# -----------------------------
def main():
    print("======================================")
    print(" Azure Dummy Website Traffic Generator ")
    print("======================================")
    print("Target:", BASE_URL)
    print("\nSelect mode:")
    print("1. Generate Normal Traffic")
    print("2. Generate Suspicious Traffic")
    print("3. Generate Brute-Force / Anomaly Traffic")
    print("4. Generate Mixed Traffic (Recommended)")
    
    choice = input("\nEnter your choice (1/2/3/4): ").strip()

    if choice == "1":
        generate_normal_traffic()
    elif choice == "2":
        generate_suspicious_traffic()
    elif choice == "3":
        generate_anomaly_traffic()
    elif choice == "4":
        generate_mixed_traffic()
    else:
        print("Invalid choice. Please run again and select 1, 2, 3, or 4.")


if __name__ == "__main__":
    main()