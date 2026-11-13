"""Run with `python3 tests/account_flow.py`; set PHP_BIN if PHP is not on PATH.

Exercises account settings and recovery against an isolated PHP server and a
private temporary data file. No real reset email is sent.
"""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, build_opener, urlopen

ROOT = Path(__file__).resolve().parents[1]


def csrf(html):
    match = re.search(r'name="csrf" value="([^"]+)', html)
    if not match:
        raise AssertionError("CSRF token not found")
    return match.group(1)


def client():
    return build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))


class AccountFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="reba-account-test-")
        cls.storage = Path(cls.tmp.name) / "private-data"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        cls.base = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update(REBA_STORAGE_DIR=str(cls.storage), REBA_BASE_URL="https://example.test")
        cls.log = open(Path(cls.tmp.name) / "server.log", "w+")
        cls.server = subprocess.Popen(
            [env.get("PHP_BIN", "php"), "-d", "sendmail_path=/bin/false", "-S", f"127.0.0.1:{port}", "-t", ".", "router.php"],
            cwd=ROOT, env=env, stdout=cls.log, stderr=cls.log,
        )
        deadline = time.monotonic() + 20
        while True:
            try:
                with urlopen(cls.base + "/home", timeout=1) as response:
                    if response.status == 200:
                        break
            except (OSError, URLError):
                if cls.server.poll() is not None or time.monotonic() >= deadline:
                    cls.tearDownClass()
                    raise RuntimeError("PHP server did not start")
                time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=10)
        cls.log.close()
        cls.tmp.cleanup()

    def get(self, c, path):
        with c.open(self.base + path) as response:
            return response.read().decode(), response.geturl()

    def post(self, c, path, values):
        with c.open(self.base + path, urlencode(values).encode()) as response:
            return response.read().decode(), response.geturl()

    def test_contact_details(self):
        page, _ = self.get(client(), "/contact")
        for text in ("Mobile / WhatsApp No.", "+91 6289459775", "tel:+916289459775", "https://wa.me/916289459775", "Stall No. 89, College Street", "(Near Calcutta University)", "Kolkata - 700009"):
            self.assertIn(text, page)
        self.assertNotIn("will be added here once confirmed", page)
        about, _ = self.get(client(), "/about")
        self.assertIn("Stall No. 89, College Street", about)

    def test_admin_inventory(self):
        admin, first, second = client(), client(), client()
        page, _ = self.get(admin, "/register")
        page, _ = self.post(admin, "/register", {"csrf": csrf(page), "action": "register", "name": "Admin Reader", "email": "ahmadmdujan@gmail.com", "password": "unverified-pass-123", "is_admin": "1"})
        self.assertIn("activate administrator access", page)
        with self.assertRaises(HTTPError) as denied:
            self.get(admin, "/admin")
        self.assertEqual(denied.exception.code, 403)
        with self.assertRaises(HTTPError) as denied:
            self.post(admin, "/admin", {"csrf": csrf(page), "action": "admin_update", "id": "history", "price": "1", "stock": "1"})
        self.assertEqual(denied.exception.code, 403)

        # Simulate receiving and using the one-time link at the designated mailbox.
        data_file = self.storage / "data.json"
        data = json.loads(data_file.read_text())
        # Simulate a catalogue saved by the previous version, with an edited price.
        data["products"]["history"]["price"] = 537
        data["products"]["history"].pop("mrp")
        uid = next(u["id"] for u in data["users"] if u["email"] == "ahmadmdujan@gmail.com")
        raw = "b" * 64
        data["password_resets"] = {hashlib.sha256(raw.encode()).hexdigest(): {"user_id": uid, "expires": int(time.time()) + 1800}}
        data_file.write_text(json.dumps(data))
        page, _ = self.get(admin, "/reset-password?token=" + raw)
        page, _ = self.post(admin, "/reset-password", {"csrf": csrf(page), "action": "reset_password", "token": raw, "new_password": "verified-pass-123", "confirm_password": "verified-pass-123"})
        page, _ = self.post(admin, "/login", {"csrf": csrf(page), "action": "login", "email": "ahmadmdujan@gmail.com", "password": "verified-pass-123"})
        self.assertIn("Manage inventory", page)
        inventory, _ = self.get(admin, "/admin")
        self.assertIn("A History of English Literature", inventory)
        self.assertIn("Untracked", inventory)
        self.assertIn("MRP (₹)", inventory)
        self.assertIn("Selling price (₹)", inventory)
        # Migrated catalogue data starts with MRP equal to its saved selling price.
        before = json.loads(data_file.read_text())["products"]["history"]
        self.assertEqual((before["mrp"], before["price"]), (537, 537))
        self.assertNotIn("% off", self.get(admin, "/book/history")[0])
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_update", "id": "history", "price": "450", "mrp": "600", "stock": "1"})
        self.assertIn("Inventory updated", inventory)
        book, _ = self.get(admin, "/book/history")
        self.assertIn("₹450", book)
        self.assertIn("₹600", book)
        self.assertIn("25% off", book)
        self.assertIn("25% off", self.get(admin, "/shop")[0])
        self.assertIn("MRP <s>₹600</s>", book)
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_update", "id": "history", "price": "500", "mrp": "600", "stock": "1"})
        self.assertIn("16.7% off", self.get(admin, "/book/history")[0])
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_update", "id": "history", "price": "450", "mrp": "600", "stock": "1"})
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_update", "id": "history", "price": "601", "mrp": "600", "stock": "1"})
        self.assertIn("selling price no higher than MRP", inventory)
        stored = json.loads(data_file.read_text())["products"]["history"]
        self.assertEqual((stored["price"], stored["mrp"]), (450, 600))
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_update", "id": "justice", "price": "0", "mrp": "100", "stock": ""})
        self.assertIn("100% off", self.get(admin, "/book/justice")[0])
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_update", "id": "justice", "price": "0", "mrp": "0", "stock": ""})
        self.assertIn("Inventory updated", inventory)
        self.assertNotIn("% off", self.get(admin, "/book/justice")[0])
        self.assertEqual(json.loads(data_file.read_text())["products"]["history"]["stock"], 1)
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_update", "id": "history", "price": "450", "mrp": "600", "stock": "-1"})
        self.assertIn("non-negative", inventory)
        self.assertEqual(json.loads(data_file.read_text())["products"]["history"]["stock"], 1)

        for number, c in enumerate((first, second)):
            page, _ = self.get(c, "/register")
            page, _ = self.post(c, "/register", {"csrf": csrf(page), "action": "register", "name": "Customer Reader", "email": f"shopper{number}@example.test", "password": "customer-pass-123"})
            with self.assertRaises(HTTPError) as denied:
                self.get(c, "/admin")
            self.assertEqual(denied.exception.code, 403)
            shop, _ = self.get(c, "/shop")
            with self.assertRaises(HTTPError) as denied:
                self.post(c, "/admin", {"csrf": csrf(shop), "action": "admin_visibility", "id": "history", "visible": "0"})
            self.assertEqual(denied.exception.code, 403)
            self.assertTrue(json.loads(data_file.read_text())["products"]["history"]["active"])
            self.post(c, "/shop", {"csrf": csrf(shop), "action": "add", "id": "history", "return": "shop"})
        checkout, _ = self.get(first, "/checkout")
        page, _ = self.post(first, "/checkout", {"csrf": csrf(checkout), "action": "checkout", "phone": "9876543210", "address": "89 College Street Kolkata 700009"})
        self.assertIn("order request has been received", page)
        checkout, _ = self.get(second, "/checkout")
        page, _ = self.post(second, "/checkout", {"csrf": csrf(checkout), "action": "checkout", "phone": "9876543210", "address": "89 College Street Kolkata 700009"})
        self.assertIn("no longer available", page)
        stored = json.loads(data_file.read_text())
        self.assertEqual(stored["products"]["history"]["stock"], 0)
        self.assertEqual(stored["orders"][-1]["items"][0]["price"], 450)
        product, _ = self.get(second, "/book/history")
        self.assertIn("Out of stock", product)
        inventory, _ = self.get(admin, "/admin")
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_visibility", "id": "history", "visible": "0"})
        self.assertIn("Book removed from the shop", inventory)
        with self.assertRaises(HTTPError) as missing:
            self.get(first, "/book/history")
        self.assertEqual(missing.exception.code, 404)
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_visibility", "id": "history", "visible": "1"})
        self.assertIn("Book restored to the shop", inventory)
        self.assertIn("A History of English Literature", self.get(first, "/book/history")[0])
        self.assertIn("A History of English Literature", self.get(first, "/account")[0])

    def test_six_character_password_minimum(self):
        c = client()
        page, _ = self.get(c, "/register")
        self.assertIn("Minimum 6 Characters", page)
        self.assertNotIn("72 bytes", page)
        for too_short in ("12345", "ééééé"):
            page, _ = self.post(c, "/register", {"csrf": csrf(page), "action": "register", "name": "Short Reader", "email": "short-password@example.test", "password": too_short})
            self.assertIn("Minimum 6 Characters", page)
        page, _ = self.post(c, "/register", {"csrf": csrf(page), "action": "register", "name": "Short Reader", "email": "short-password@example.test", "password": "x" * 73})
        self.assertIn("Please use a shorter password", page)
        page, url = self.post(c, "/register", {"csrf": csrf(page), "action": "register", "name": "Short Reader", "email": "short-password@example.test", "password": "ab1234"})
        self.assertTrue(url.endswith("/account"))
        page, _ = self.post(c, "/account", {"csrf": csrf(page), "action": "change_password", "current_password": "ab1234", "new_password": "12345", "confirm_password": "12345"})
        self.assertIn("Minimum 6 Characters", page)
        page, _ = self.post(c, "/account", {"csrf": csrf(page), "action": "change_password", "current_password": "ab1234", "new_password": "éabcd1", "confirm_password": "éabcd1"})
        self.assertIn("Your password has been updated", page)
        page, _ = self.post(c, "/account", {"csrf": csrf(page), "action": "logout"})
        page, _ = self.get(c, "/login")
        page, url = self.post(c, "/login", {"csrf": csrf(page), "action": "login", "email": "short-password@example.test", "password": "éabcd1"})
        self.assertTrue(url.endswith("/account"))
        data_file = self.storage / "data.json"
        data = json.loads(data_file.read_text())
        uid = next(u["id"] for u in data["users"] if u["email"] == "short-password@example.test")
        raw = "c" * 64
        data["password_resets"] = {hashlib.sha256(raw.encode()).hexdigest(): {"user_id": uid, "expires": int(time.time()) + 1800}}
        data_file.write_text(json.dumps(data))
        page, _ = self.get(c, "/reset-password?token=" + raw)
        page, _ = self.post(c, "/reset-password", {"csrf": csrf(page), "action": "reset_password", "token": raw, "new_password": "123456", "confirm_password": "123456"})
        self.assertIn("Your password has been reset", page)
        page, url = self.post(c, "/login", {"csrf": csrf(page), "action": "login", "email": "short-password@example.test", "password": "123456"})
        self.assertTrue(url.endswith("/account"))

    def test_default_recovery_origin_is_pinned(self):
        env = os.environ.copy()
        env.pop("REBA_BASE_URL", None)
        env["REBA_STORAGE_DIR"] = str(self.storage)
        php = env.get("PHP_BIN", "php")

        def config(host):
            code = (
                '$_SERVER["SCRIPT_NAME"]="/index.php"; '
                '$_SERVER["REQUEST_URI"]="/contact"; '
                '$_SERVER["REQUEST_METHOD"]="GET"; '
                '$_SERVER["HTTP_HOST"]=' + json.dumps(host) + '; '
                'ob_start(); require "index.php"; ob_end_clean(); echo json_encode(resetConfig());'
            )
            result = subprocess.run([php, "-r", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)

        expected = {"base": "https://rebabooksociety.websolve.co.in", "from": "info@rebabooksociety.websolve.co.in"}
        self.assertEqual(config("rebabooksociety.websolve.co.in"), expected)
        self.assertEqual(config("rebabooksociety.websolve.co.in:443"), expected)
        self.assertIsNone(config("rebabooksociety.websolve.co.in.attacker.example"))
        self.assertIsNone(config("preview.example"))

    def test_account_and_recovery(self):
        first, second = client(), client()
        page, _ = self.get(first, "/register")
        page, url = self.post(first, "/register", {
            "csrf": csrf(page), "action": "register", "name": "First Reader",
            "email": "account-test@example.test", "password": "original-pass-123",
        })
        self.assertTrue(url.endswith("/account"))
        self.assertIn("Account settings", page)
        page, _ = self.post(first, "/account", {
            "csrf": csrf(page), "action": "save_profile", "name": "Updated Reader",
            "shipping_address": "89 College Street Kolkata 700009", "billing_address": "Billing address Kolkata 700009",
        })
        self.assertIn("Updated", page)
        self.assertIn("Billing address Kolkata 700009", page)
        checkout, _ = self.get(first, "/checkout")
        self.assertIn("89 College Street Kolkata 700009", checkout)

        login, _ = self.get(second, "/login")
        page2, url = self.post(second, "/login", {"csrf": csrf(login), "action": "login", "email": "account-test@example.test", "password": "original-pass-123"})
        self.assertTrue(url.endswith("/account"))
        page, _ = self.post(first, "/account", {"csrf": csrf(page), "action": "change_password", "current_password": "wrong-password", "new_password": "changed-pass-123", "confirm_password": "changed-pass-123"})
        self.assertIn("Current password is incorrect", page)
        page, _ = self.post(first, "/account", {"csrf": csrf(page), "action": "change_password", "current_password": "original-pass-123", "new_password": "changed-pass-123", "confirm_password": "changed-pass-123"})
        self.assertIn("Your password has been updated", page)
        _, url = self.get(second, "/account")
        self.assertTrue(url.endswith("/login"))
        login, _ = self.get(second, "/login")
        _, url = self.post(second, "/login", {"csrf": csrf(login), "action": "login", "email": "account-test@example.test", "password": "changed-pass-123"})
        self.assertTrue(url.endswith("/account"))
        with self.assertRaises(HTTPError) as denied:
            self.post(first, "/account", {"csrf": "wrong", "action": "save_profile", "name": "Changed"})
        self.assertEqual(denied.exception.code, 403)

        page, _ = self.get(first, "/forgot-password")
        page, _ = self.post(first, "/forgot-password", {"csrf": csrf(page), "action": "forgot_password", "email": "account-test@example.test"})
        self.assertIn("If an account exists", page)
        data_file = self.storage / "data.json"
        data = json.loads(data_file.read_text())
        self.assertEqual(len(data["password_resets"]), 1)
        self.assertNotIn("changed-pass-123", data_file.read_text())

        # Mail delivery is disabled in this test. Insert a known token hash to
        # exercise expiry, reset, and one-time use without a real mail service.
        raw = "a" * 64
        digest = hashlib.sha256(raw.encode()).hexdigest()
        uid = data["users"][0]["id"]
        data["password_resets"] = {digest: {"user_id": uid, "expires": int(time.time()) - 1}}
        data_file.write_text(json.dumps(data))
        page, _ = self.get(first, "/reset-password?token=" + raw)
        page, _ = self.post(first, "/reset-password", {"csrf": csrf(page), "action": "reset_password", "token": raw, "new_password": "recovered-pass-123", "confirm_password": "recovered-pass-123"})
        self.assertIn("invalid or has expired", page)
        data = json.loads(data_file.read_text())
        data["password_resets"] = {digest: {"user_id": uid, "expires": int(time.time()) + 1800}}
        data_file.write_text(json.dumps(data))
        page, _ = self.get(first, "/reset-password?token=" + raw)
        page, url = self.post(first, "/reset-password", {"csrf": csrf(page), "action": "reset_password", "token": raw, "new_password": "recovered-pass-123", "confirm_password": "recovered-pass-123"})
        self.assertTrue(url.endswith("/login"))
        self.assertIn("Your password has been reset", page)
        _, url = self.get(second, "/account")
        self.assertTrue(url.endswith("/login"))
        page, _ = self.get(first, "/reset-password?token=" + raw)
        page, _ = self.post(first, "/reset-password", {"csrf": csrf(page), "action": "reset_password", "token": raw, "new_password": "another-pass-123", "confirm_password": "another-pass-123"})
        self.assertIn("invalid or has expired", page)
        page, _ = self.get(second, "/login")
        _, url = self.post(second, "/login", {"csrf": csrf(page), "action": "login", "email": "account-test@example.test", "password": "recovered-pass-123"})
        self.assertTrue(url.endswith("/account"))


if __name__ == "__main__":
    unittest.main()
