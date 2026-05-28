import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error
import re

def run_tests():
    token = "test_opaque_token_12345"
    env = os.environ.copy()
    env["AGENT_SECRET_TOKEN"] = token
    env["PYTHONUNBUFFERED"] = "1"
    
    # Spawn the Robyn server
    print("Starting Robyn backend sidecar for testing...")
    process = subprocess.Popen(
        ["uv", "run", "python", "-u", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd="/Users/woodman/dev/erth_assistant_reborn/src-app/backend",
        env=env,
        text=True
    )
    
    port = None
    # Wait for the server to output the port. We parse stdout for the port.
    start_time = time.time()
    while time.time() - start_time < 10:
        line = process.stdout.readline()
        if not line:
            # Check if process died
            if process.poll() is not None:
                err = process.stderr.read()
                print(f"Process exited prematurely: {err}")
                return False
            time.sleep(0.1)
            continue
            
        print(f"[Robyn STDOUT] {line.strip()}")
        # Parse port using regex matching
        match = re.search(r"http://127\.0\.0\.1:(\d+)|listening on: [^:]+:(\d+)", line)
        if match:
            raw_port = match.group(1) or match.group(2)
            if raw_port:
                val = int(raw_port)
                if val > 0:
                    port = val
                    print(f"Detected port: {port}")
                    break
                    
    if not port:
        print("Failed to detect port within 10 seconds.")
        process.terminate()
        return False
        
    base_url = f"http://127.0.0.1:{port}"
    
    # Helper to make requests
    def make_request(path, method="GET", body=None, use_token=True, custom_token=None):
        url = f"{base_url}{path}"
        headers = {}
        if use_token:
            headers["Authorization"] = f"Bearer {custom_token or token}"
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        else:
            data = None
            
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as response:
                resp_body = response.read().decode("utf-8")
                return response.status, json.loads(resp_body) if resp_body else None
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8")
            try:
                err_data = json.loads(resp_body)
            except Exception:
                err_data = resp_body
            return e.code, err_data
        except Exception as e:
            print(f"Request failed: {e}")
            return None, None

    success = True
    try:
        # Give server a tiny moment to settle
        time.sleep(0.5)
        
        # 1. Test ping
        print("\n--- Test 1: GET /ping (with token) ---")
        status, res = make_request("/ping")
        print(f"Status: {status}, Response: {res}")
        if status != 200 or not res or res.get("status") != "pong":
            print("Ping test failed.")
            success = False

        # 2. Test forbidden access (no token)
        print("\n--- Test 2: GET /ping (no token) ---")
        status, res = make_request("/ping", use_token=False)
        print(f"Status: {status}, Response: {res}")
        if status != 403:
            print("Auth bypass test failed (expected 403).")
            success = False

        # 3. Test forbidden access (invalid token)
        print("\n--- Test 3: GET /ping (invalid token) ---")
        status, res = make_request("/ping", custom_token="wrong_token")
        print(f"Status: {status}, Response: {res}")
        if status != 403:
            print("Auth invalid token test failed (expected 403).")
            success = False

        # 4. Test health check
        print("\n--- Test 4: GET /api/v1/health ---")
        status, res = make_request("/api/v1/health")
        print(f"Status: {status}, Response: {res}")
        if status != 200 or not res or res.get("status") != "success":
            print("Health check test failed.")
            success = False

        # 5. Test get active todos (should contain sentinel)
        print("\n--- Test 5: GET /api/v1/todos (initial) ---")
        status, res = make_request("/api/v1/todos")
        print(f"Status: {status}, Response: {res}")
        if status != 200 or not isinstance(res, list) or len(res) == 0:
            print("GET /api/v1/todos test failed.")
            success = False
        else:
            print(f"Initial list count: {len(res)}")
            sentinel = res[0]
            print(f"Sentinel todo: {sentinel}")

        # 6. Test post new todo
        print("\n--- Test 6: POST /api/v1/todos ---")
        status, new_todo = make_request("/api/v1/todos", method="POST", body={"title": "Test Chapter 5 Verification"})
        print(f"Status: {status}, Response: {new_todo}")
        if status != 201 or not new_todo or new_todo.get("title") != "Test Chapter 5 Verification":
            print("POST /api/v1/todos test failed.")
            success = False
            todo_id = None
        else:
            todo_id = new_todo.get("id")
            print(f"Created todo ID: {todo_id}")

        if todo_id:
            # 7. Test get todos list again (should contain new todo)
            print("\n--- Test 7: GET /api/v1/todos (after post) ---")
            status, res = make_request("/api/v1/todos")
            print(f"Status: {status}, Count: {len(res) if res else 0}")
            if status != 200 or not res or not any(t.get("id") == todo_id for t in res):
                print("New todo not found in the list.")
                success = False

            # 8. Test toggle status
            print("\n--- Test 8: PUT /api/v1/todos/:id/toggle (to completed) ---")
            status, toggled = make_request(f"/api/v1/todos/{todo_id}/toggle", method="PUT")
            print(f"Status: {status}, Response: {toggled}")
            if status != 200 or not toggled or toggled.get("is_completed") != 1:
                print("Toggle status to completed failed.")
                success = False

            print("\n--- Test 9: PUT /api/v1/todos/:id/toggle (back to active) ---")
            status, toggled = make_request(f"/api/v1/todos/{todo_id}/toggle", method="PUT")
            print(f"Status: {status}, Response: {toggled}")
            if status != 200 or not toggled or toggled.get("is_completed") != 0:
                print("Toggle status back to active failed.")
                success = False

            # 9. Test soft delete
            print("\n--- Test 10: DELETE /api/v1/todos/:id ---")
            status, deleted = make_request(f"/api/v1/todos/{todo_id}", method="DELETE")
            print(f"Status: {status}, Response: {deleted}")
            if status != 200 or not deleted or deleted.get("status") != "success":
                print("Delete todo failed.")
                success = False

            # 10. Test get active todos (should not contain the deleted one)
            print("\n--- Test 11: GET /api/v1/todos (after delete) ---")
            status, res = make_request("/api/v1/todos")
            print(f"Status: {status}, Count: {len(res) if res else 0}")
            if status != 200 or (res and any(t.get("id") == todo_id for t in res)):
                print("Deleted todo still found in active list.")
                success = False

            # 11. Test toggle deleted todo (should return 404)
            print("\n--- Test 12: PUT /api/v1/todos/:id/toggle (on deleted) ---")
            status, res = make_request(f"/api/v1/todos/{todo_id}/toggle", method="PUT")
            print(f"Status: {status}, Response: {res}")
            if status != 404:
                print("Expected 404 when toggling deleted todo.")
                success = False

            # 12. Test delete deleted todo (should return 404)
            print("\n--- Test 13: DELETE /api/v1/todos/:id (on deleted) ---")
            status, res = make_request(f"/api/v1/todos/{todo_id}", method="DELETE")
            print(f"Status: {status}, Response: {res}")
            if status != 404:
                print("Expected 404 when deleting already deleted todo.")
                success = False
                
    finally:
        print("\nTerminating Robyn backend process...")
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            
    return success

if __name__ == "__main__":
    result = run_tests()
    if result:
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! Chapter 5 is fully verified.")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED.")
        sys.exit(1)
