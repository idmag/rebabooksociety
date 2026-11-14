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
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

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
                with urlopen(cls.base + "/", timeout=1) as response:
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

    def test_homepage_canonical_url(self):
        c = client()
        page, final_url = self.get(c, "/")
        self.assertEqual(final_url, self.base + "/")
        nav = page.split('<nav class="main-nav"', 1)[1].split('</nav>', 1)[0]
        self.assertRegex(nav, r'<a class="active" aria-current="page" href="/">Home</a>')
        for old in ("/home", "/home/", "/index.php", "/?page=home"):
            _, final_url = self.get(c, old)
            self.assertEqual(final_url, self.base + "/")
        _, final_url = self.get(c, "/home?source=bookmark")
        self.assertEqual(final_url, self.base + "/?source=bookmark")
        _, final_url = self.get(c, "/home?category=Drama")
        self.assertEqual(final_url, self.base + "/shop?category=Drama#collection")

    def test_cart_add_feedback(self):
        c = client()
        page, _ = self.get(c, "/")
        page, url = self.post(c, "/", {"csrf": csrf(page), "action": "add", "id": "perseus", "return": "home"})
        self.assertTrue(url.endswith("/#product-perseus"))
        self.assertIn('“Perseus the Deliverer” has been added to your cart.</span>', page)
        self.assertIn('data-cart-quantity>1 in cart</span>', page)
        page, url = self.post(c, "/shop?category=Drama&q=Perseus", {"csrf": csrf(page), "action": "add", "id": "perseus", "return": "shop"})
        self.assertTrue(url.endswith("/shop?category=Drama&q=Perseus#product-perseus"))
        self.assertIn('“Perseus the Deliverer” has been added to your cart.</span>', page)
        self.assertIn('data-cart-quantity>2 in cart</span>', page)
        page, _ = self.get(c, "/book/perseus")
        self.assertNotIn('has been added to your cart', page)
        page, url = self.post(c, "/book/perseus", {"csrf": csrf(page), "action": "add", "id": "perseus", "return": "book"})
        self.assertTrue(url.endswith("/book/perseus#product-perseus"))
        self.assertIn('“Perseus the Deliverer” has been added to your cart.</span>', page)
        self.assertIn('data-cart-quantity>3 in cart</span>', page)
        self.assertIn('href="/cart">View cart', page)
        page, url = self.post(c, "/shop", {"csrf": csrf(page), "action": "add", "id": "missing", "return": "book"})
        self.assertTrue(url.endswith("/shop#cart-feedback"))
        self.assertIn('This book is no longer available.', page)
        self.assertNotIn('has been added to your cart', page)

    def test_cart_add_ajax_and_delete(self):
        c = client()
        page, _ = self.get(c, "/shop?category=Drama")
        token = csrf(page)
        def add(item):
            fields = {"csrf": token, "action": "add", "id": item, "return": "shop"}
            boundary = "reba-test-boundary"
            body = b"".join((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode() for key, value in fields.items()) + f'--{boundary}--\r\n'.encode()
            request = Request(self.base + "/shop?category=Drama", body, headers={"Accept": "application/json", "Content-Type": "multipart/form-data; boundary=" + boundary})
            with c.open(request) as response:
                self.assertEqual(response.headers.get_content_type(), "application/json")
                return json.loads(response.read())
        self.assertEqual(add("perseus")["quantity"], 1)
        result = add("perseus")
        self.assertEqual((result["success"], result["quantity"], result["cartCount"]), (True, 2, 2))
        self.assertEqual(result["message"], "“Perseus the Deliverer” has been added to your cart.")
        self.assertEqual(add("wasteland")["cartCount"], 3)
        cart, _ = self.get(c, "/cart")
        self.assertIn('name="remove_id" value="perseus"', cart)
        self.assertIn('name="remove_id" value="wasteland"', cart)
        # Removing one item does not apply unsaved quantity fields to another item.
        cart, _ = self.post(c, "/cart", {"csrf": csrf(cart), "action": "update_cart", "remove_id": "perseus", "qty[wasteland]": "0"})
        self.assertNotIn('name="remove_id" value="perseus"', cart)
        self.assertIn('name="remove_id" value="wasteland"', cart)
        self.assertIn('Book removed from your cart.', cart)
        page, _ = self.get(c, "/book/perseus")
        self.assertIn('data-cart-quantity hidden>0 in cart</span>', page)
        cart, _ = self.post(c, "/cart", {"csrf": csrf(cart), "action": "update_cart", "remove_id": "wasteland"})
        self.assertIn('Your bag is waiting', cart)

    def test_cart_auto_update_response(self):
        c = client()
        page, _ = self.get(c, "/book/perseus")
        self.assertIn('data-cart-quantity hidden>0 in cart</span>', page)
        self.assertIn('data-cart-badge hidden>0</span>', page)
        page, _ = self.post(c, "/book/perseus", {"csrf": csrf(page), "action": "add", "id": "perseus", "return": "book"})
        cart, _ = self.get(c, "/cart")
        self.assertIn('cart-update.js', cart)
        self.assertIn('data-cart-form', cart)
        self.assertNotIn('Set quantity to 0 to remove a book.', cart)
        self.assertIn('name="remove_id" value="perseus"', cart)
        data = urlencode({"csrf": csrf(cart), "action": "update_cart", "qty[perseus]": "3"}).encode()
        request = Request(self.base + "/cart", data, headers={"Accept": "application/json"})
        with c.open(request) as response:
            self.assertEqual(response.headers.get_content_type(), "application/json")
            saved = json.loads(response.read())
        self.assertEqual(saved['items']['perseus']['quantity'], 3)
        self.assertEqual(saved['items']['perseus']['lineTotal'], '₹747')
        self.assertEqual(saved['subtotal'], '₹747')
        self.assertEqual(saved['cartCount'], 3)
        cart, _ = self.get(c, "/cart")
        self.assertIn('value="3"', cart)
        self.assertNotIn('class="notice"', cart)
        data = urlencode({"csrf": csrf(cart), "action": "update_cart", "qty[perseus]": "0"}).encode()
        with c.open(Request(self.base + "/cart", data, headers={"Accept": "application/json"})) as response:
            saved = json.loads(response.read())
        self.assertEqual(saved['cartCount'], 0)
        self.assertFalse(saved['items'])
        page, _ = self.get(c, "/book/perseus")
        self.assertIn('data-cart-quantity hidden>0 in cart</span>', page)
        self.assertIn('data-cart-badge hidden>0</span>', page)

    def test_wishlist_guest_and_account_persistence(self):
        guest = client()
        page, _ = self.get(guest, "/wishlist")
        self.assertIn('Your wishlist is empty.', page)
        self.assertIn('data-wishlist-badge hidden>0</span>', page)
        shop, _ = self.get(guest, "/shop?category=Drama")
        self.assertIn('aria-label="Add Perseus the Deliverer to wishlist"', shop)
        with self.assertRaises(HTTPError) as denied:
            self.post(guest, "/shop", {"csrf": "wrong", "action": "wishlist_toggle", "id": "perseus", "set": "1"})
        self.assertEqual(denied.exception.code, 403)
        page, url = self.post(guest, "/shop?category=Drama", {"csrf": csrf(shop), "action": "wishlist_toggle", "id": "perseus", "set": "1", "return": "shop"})
        self.assertTrue(url.endswith('/shop?category=Drama#product-perseus'))
        self.assertIn('data-wishlist-badge>1</span>', page)
        self.assertIn('aria-label="Remove Perseus the Deliverer from wishlist"', page)
        page, _ = self.get(guest, "/wishlist")
        self.assertIn('Perseus the Deliverer', page)
        self.assertIn('name="return" value="wishlist"', page)
        # Repeated adds are idempotent, and a saved book can be added to the cart.
        request = Request(self.base + '/wishlist', urlencode({"csrf": csrf(page), "action": "wishlist_toggle", "id": "perseus", "set": "1"}).encode(), headers={"Accept": "application/json"})
        with guest.open(request) as response:
            self.assertEqual(json.loads(response.read())['count'], 1)
        page, url = self.post(guest, "/wishlist", {"csrf": csrf(page), "action": "add", "id": "perseus", "return": "wishlist"})
        self.assertTrue(url.endswith('/wishlist#product-perseus'))
        self.assertIn('has been added to your cart', page)
        self.assertIn('data-cart-quantity>1 in cart</span>', page)
        page, _ = self.get(guest, "/register")
        page, _ = self.post(guest, "/register", {"csrf": csrf(page), "action": "register", "name": "Wishlist Reader", "email": "wishlist-reader@example.test", "password": "reading123"})
        data = json.loads((self.storage / 'data.json').read_text())
        account = next(u for u in data['users'] if u['email'] == 'wishlist-reader@example.test')
        self.assertEqual(account['wishlist'], ['perseus'])
        page, _ = self.post(guest, "/account", {"csrf": csrf(page), "action": "logout"})
        page, _ = self.get(guest, "/wishlist")
        self.assertIn('Your wishlist is empty.', page)
        # A fresh session merges its own guest saves on sign-in without duplicates.
        other = client()
        page, _ = self.get(other, "/shop")
        page, _ = self.post(other, "/shop", {"csrf": csrf(page), "action": "wishlist_toggle", "id": "wasteland", "set": "1", "return": "shop"})
        login, _ = self.get(other, "/login")
        page, _ = self.post(other, "/login", {"csrf": csrf(login), "action": "login", "email": "wishlist-reader@example.test", "password": "reading123"})
        page, _ = self.get(other, "/wishlist")
        self.assertIn('Perseus the Deliverer', page)
        self.assertIn('The Waste Land and Other Poems', page)
        self.assertIn('data-wishlist-badge>2</span>', page)
        # Unsaving persists for the account, and does not affect the guest session.
        request = Request(self.base + '/wishlist', urlencode({"csrf": csrf(page), "action": "wishlist_toggle", "id": "perseus", "set": "0"}).encode(), headers={"Accept": "application/json"})
        with other.open(request) as response:
            result = json.loads(response.read())
        self.assertEqual((result['saved'], result['count']), (False, 1))
        data = json.loads((self.storage / 'data.json').read_text())
        account = next(u for u in data['users'] if u['email'] == 'wishlist-reader@example.test')
        self.assertEqual(account['wishlist'], ['wasteland'])
        second_account = client()
        page, _ = self.get(second_account, "/register")
        page, _ = self.post(second_account, "/register", {"csrf": csrf(page), "action": "register", "name": "Another Reader", "email": "wishlist-other@example.test", "password": "reading123"})
        page, _ = self.get(second_account, "/wishlist")
        self.assertIn('Your wishlist is empty.', page)
        page, _ = self.get(other, "/wishlist")
        page, _ = self.post(other, "/wishlist", {"csrf": csrf(page), "action": "wishlist_toggle", "id": "wasteland", "set": "0", "return": "wishlist"})
        self.assertIn('Your wishlist is empty.', page)
        self.assertNotIn('id="product-wasteland"', page)
        page, _ = self.get(guest, "/wishlist")
        self.assertIn('Your wishlist is empty.', page)
        page, _ = self.get(guest, "/shop")
        request = Request(self.base + '/shop', urlencode({"csrf": csrf(page), "action": "wishlist_toggle", "id": "missing", "set": "1"}).encode(), headers={"Accept": "application/json"})
        with self.assertRaises(HTTPError) as denied:
            guest.open(request)
        self.assertEqual(denied.exception.code, 400)

    def test_remove_all_cart_and_wishlist(self):
        c, another = client(), client()
        shop, _ = self.get(c, "/shop")
        other_shop, _ = self.get(another, "/shop")
        for book in ('perseus', 'wasteland'):
            shop, _ = self.post(c, "/shop", {"csrf": csrf(shop), "action": "add", "id": book, "return": "shop"})
            shop, _ = self.post(c, "/shop", {"csrf": csrf(shop), "action": "wishlist_toggle", "id": book, "set": "1", "return": "shop"})
        self.post(another, "/shop", {"csrf": csrf(other_shop), "action": "wishlist_toggle", "id": "perseus", "set": "1", "return": "shop"})
        cart, _ = self.get(c, "/cart")
        self.assertIn('data-clear-cart', cart)
        self.assertIn('>Remove All</button>', cart)
        with self.assertRaises(HTTPError) as denied:
            self.post(c, "/cart", {"csrf": "bad", "action": "clear_cart"})
        self.assertEqual(denied.exception.code, 403)
        self.assertIn('data-cart-row="perseus"', self.get(c, "/cart")[0])
        cart, _ = self.post(c, "/cart", {"csrf": csrf(cart), "action": "clear_cart"})
        self.assertIn('All books have been removed from your cart.', cart)
        self.assertIn('Your bag is waiting', cart)
        self.assertNotIn('data-clear-cart', cart)
        wishlist, _ = self.get(c, "/wishlist")
        self.assertIn('data-clear-wishlist', wishlist)
        self.assertIn('id="product-perseus"', wishlist)
        self.assertIn('id="product-wasteland"', wishlist)
        with self.assertRaises(HTTPError) as denied:
            self.post(c, "/wishlist", {"csrf": "bad", "action": "wishlist_clear"})
        self.assertEqual(denied.exception.code, 403)
        self.assertIn('id="product-perseus"', self.get(c, "/wishlist")[0])
        wishlist, _ = self.post(c, "/wishlist", {"csrf": csrf(wishlist), "action": "wishlist_clear"})
        self.assertIn('All books have been removed from your wishlist.', wishlist)
        self.assertIn('Your wishlist is empty.', wishlist)
        self.assertNotIn('data-clear-wishlist', wishlist)
        self.assertIn('id="product-perseus"', self.get(another, "/wishlist")[0])

    def test_remove_all_account_wishlist_persists(self):
        c = client()
        page, _ = self.get(c, "/register")
        page, _ = self.post(c, "/register", {"csrf": csrf(page), "action": "register", "name": "Clear Reader", "email": "clear-wishlist@example.test", "password": "reading123"})
        shop, _ = self.get(c, "/shop")
        for book in ('perseus', 'wasteland'):
            shop, _ = self.post(c, "/shop", {"csrf": csrf(shop), "action": "wishlist_toggle", "id": book, "set": "1", "return": "shop"})
        page, _ = self.get(c, "/wishlist")
        page, _ = self.post(c, "/wishlist", {"csrf": csrf(page), "action": "wishlist_clear"})
        self.assertIn('Your wishlist is empty.', page)
        data = json.loads((self.storage / 'data.json').read_text())
        account = next(u for u in data['users'] if u['email'] == 'clear-wishlist@example.test')
        self.assertEqual(account['wishlist'], [])
        account_page, _ = self.get(c, "/account")
        self.post(c, "/account", {"csrf": csrf(account_page), "action": "logout"})
        login, _ = self.get(c, "/login")
        self.post(c, "/login", {"csrf": csrf(login), "action": "login", "email": "clear-wishlist@example.test", "password": "reading123"})
        page, _ = self.get(c, "/wishlist")
        self.assertIn('Your wishlist is empty.', page)

    def test_home_featured_books(self):
        page, _ = self.get(client(), "/")
        shelf = page.split('id="featured-books"', 1)[1].split('</div><div class="featured-carousel-bar">', 1)[0]
        self.assertEqual(shelf.count('class="book-card"'), 4)
        self.assertIn('data-featured-prev', page)
        self.assertIn('data-featured-next', page)
        self.assertIn('featured-carousel.js', page)
        with urlopen(self.base + "/assets/featured-carousel.js") as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'scrollBy', response.read())
        shop, _ = self.get(client(), "/shop")
        self.assertEqual(shop.count('class="book-card"'), 7)
        self.assertNotIn('featured-carousel.js', shop)

    def test_favicon(self):
        page, _ = self.get(client(), "/")
        self.assertIn('href="/assets/favicon.ico"', page)
        self.assertIn('href="/assets/favicon.png"', page)
        for path in ("/assets/favicon.ico", "/assets/favicon.png"):
            with urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200)
                self.assertGreater(len(response.read()), 100)

    def test_announcement_contact_links(self):
        for path in ("/", "/contact"):
            page, _ = self.get(client(), path)
            strip = page.split('<div class="announcement">', 1)[1].split('</div>', 1)[0]
            self.assertIn('href="tel:+916289459775"', strip)
            self.assertIn('href="https://wa.me/916289459775"', strip)
            self.assertIn('+91 6289459775', strip)
            self.assertIn('aria-label="Call Reba Book Society"', strip)
            self.assertIn('aria-label="Chat with Reba Book Society on WhatsApp"', strip)
            self.assertEqual(strip.count('<svg'), 2)
            self.assertNotIn('COLLEGE STREET, KOLKATA', strip)

    def test_navigation(self):
        for path, label in (("/", "Home"), ("/shop", "Shop"), ("/book/history", "Shop"), ("/about", "About Us"), ("/contact", "Contact")):
            page, _ = self.get(client(), path)
            nav = page.split('<nav class="main-nav"', 1)[1].split('</nav>', 1)[0]
            self.assertRegex(nav, r'<a class="active" aria-current="page" href="[^"]+">' + re.escape(label) + r'</a>')
            self.assertEqual(nav.count('aria-current="page"'), 1)
            self.assertIn('Shop', nav)
            self.assertIn('About Us', nav)

    def test_footer_link_capitalisation(self):
        page, _ = self.get(client(), "/")
        footer = page.split("<footer>", 1)[1].split("</footer>", 1)[0]
        for label in ("Shop All Books", "Our Story", "Visit Us", "Contact", "My Account", "My Orders", "Shopping Bag"):
            self.assertIn(">" + label + "</a>", footer)

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
        self.assertIn(">Manage Inventory</a>", page.split("<footer>", 1)[1])
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
            added, _ = self.post(c, "/shop", {"csrf": csrf(shop), "action": "add", "id": "history", "return": "shop"})
            self.assertIn("“A History of English Literature” has been added to your cart.</span>", added)
        first_shop, _ = self.get(first, "/shop")
        limited, _ = self.post(first, "/shop", {"csrf": csrf(first_shop), "action": "add", "id": "history", "return": "shop"})
        self.assertIn("could not be added", limited)
        self.assertIn('data-cart-quantity>1 in cart</span>', limited)
        self.assertNotIn("copy of this book", limited)
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
        page, _ = self.get(first, "/book/history")
        hidden_guest = client()
        guest_product, _ = self.get(hidden_guest, "/book/history")
        self.post(hidden_guest, "/book/history", {"csrf": csrf(guest_product), "action": "wishlist_toggle", "id": "history", "set": "1", "return": "book"})
        page, _ = self.post(first, "/book/history", {"csrf": csrf(page), "action": "wishlist_toggle", "id": "history", "set": "1", "return": "book"})
        self.assertIn('Saved to Wishlist', page)  # Out-of-stock books can still be saved.
        inventory, _ = self.get(admin, "/admin")
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_visibility", "id": "history", "visible": "0"})
        self.assertIn("Book removed from the shop", inventory)
        wishlist, _ = self.get(first, "/wishlist")
        self.assertIn('Some saved books are currently unavailable', wishlist)
        self.assertNotIn('id="product-history"', wishlist)
        guest_wishlist, _ = self.get(hidden_guest, "/wishlist")
        self.assertIn('data-clear-wishlist', guest_wishlist)
        guest_wishlist, _ = self.post(hidden_guest, "/wishlist", {"csrf": csrf(guest_wishlist), "action": "wishlist_clear"})
        self.assertNotIn('Some saved books are currently unavailable', guest_wishlist)
        shop, _ = self.get(second, "/shop")
        request = Request(self.base + '/shop', urlencode({"csrf": csrf(shop), "action": "wishlist_toggle", "id": "history", "set": "1"}).encode(), headers={"Accept": "application/json"})
        with self.assertRaises(HTTPError) as denied:
            second.open(request)
        self.assertEqual(denied.exception.code, 400)
        with self.assertRaises(HTTPError) as missing:
            self.get(first, "/book/history")
        self.assertEqual(missing.exception.code, 404)
        inventory, _ = self.post(admin, "/admin", {"csrf": csrf(inventory), "action": "admin_visibility", "id": "history", "visible": "1"})
        self.assertIn("Book restored to the shop", inventory)
        self.assertIn("A History of English Literature", self.get(first, "/book/history")[0])
        self.assertIn('id="product-history"', self.get(first, "/wishlist")[0])
        self.assertNotIn('id="product-history"', self.get(hidden_guest, "/wishlist")[0])
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
