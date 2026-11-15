"""OAuth initiation and state tests with synthetic credentials; no Google network calls.
Run: PHP_BIN=/path/to/php python3 tests/google_oauth_flow.py
"""
import http.cookiejar
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request

ROOT = Path(__file__).resolve().parents[1]
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

class OAuthFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='reba-oauth-test-')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        env = os.environ.copy()
        env.update(REBA_STORAGE_DIR=str(Path(cls.tmp.name)/'private'), REBA_BASE_URL='https://example.test', REBA_GOOGLE_CLIENT_ID='12345-example.apps.googleusercontent.com', REBA_GOOGLE_CLIENT_SECRET='test-secret')
        cls.log = open(Path(cls.tmp.name)/'server.log', 'w+')
        cls.server = subprocess.Popen([env.get('PHP_BIN','php'), '-S', f'127.0.0.1:{port}', '-t', '.', 'router.php'], cwd=ROOT, env=env, stdout=cls.log, stderr=cls.log)
        deadline=time.monotonic()+20
        while True:
            try:
                with build_opener().open(cls.base+'/login',timeout=1): break
            except (OSError,URLError):
                if cls.server.poll() is not None or time.monotonic()>deadline: raise RuntimeError('Server failed to start')
                time.sleep(.05)
    @classmethod
    def tearDownClass(cls):
        cls.server.terminate(); cls.server.wait(timeout=10); cls.log.close(); cls.tmp.cleanup()
    def setUp(self):
        self.client=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect())
    def request(self, path, data=None):
        try: return self.client.open(Request(self.base+path, urlencode(data).encode() if data is not None else None))
        except HTTPError as e: return e
    def csrf(self, path='/login'):
        page=self.request(path).read().decode(); return re.search(r'name="csrf" value="([^"]+)',page).group(1)
    def test_start_state_pkce_and_one_time_state(self):
        csrf=self.csrf()
        response=self.request('/login',{'csrf':csrf,'action':'google_start','next':'checkout'})
        self.assertEqual(response.status,302)
        location=response.headers['Location']; parts=urlsplit(location); query=parse_qs(parts.query)
        self.assertEqual(parts.netloc,'accounts.google.com')
        self.assertEqual(query['redirect_uri'],['https://example.test/google-callback'])
        self.assertEqual(query['scope'],['openid email profile'])
        self.assertEqual(query['code_challenge_method'],['S256'])
        self.assertNotIn('test-secret',location)
        state=query['state'][0]
        response=self.request('/google-callback?'+urlencode({'state':'wrong','code':'fake'}))
        self.assertEqual(response.headers['Location'],'/login')
        # A mismatched callback consumes the transaction; replay cannot exchange a code.
        response=self.request('/google-callback?'+urlencode({'state':state,'code':'fake'}))
        self.assertEqual(response.headers['Location'],'/login')
    def test_start_requires_csrf_and_link_requires_login(self):
        self.assertEqual(self.request('/login',{'action':'google_start','csrf':'wrong'}).status,403)
        csrf=self.csrf()
        self.assertEqual(self.request('/login',{'action':'google_link','csrf':csrf}).headers['Location'],'/login')
        self.assertEqual(self.request('/google-oauth.php').status,404)
    def test_existing_user_can_start_link_and_cancel(self):
        page=self.request('/register').read().decode()
        token=re.search(r'name="csrf" value="([^"]+)',page).group(1)
        response=self.request('/register',{'action':'register','csrf':token,'name':'Link Reader','email':'link-reader@example.test','password':'reading123'})
        self.assertEqual(response.headers['Location'],'/account')
        page=self.request('/account').read().decode()
        self.assertIn('Link Google',page)
        token=re.search(r'name="csrf" value="([^"]+)',page).group(1)
        location=self.request('/account',{'action':'google_link','csrf':token}).headers['Location']
        state=parse_qs(urlsplit(location).query)['state'][0]
        self.assertEqual(self.request('/google-callback?'+urlencode({'state':state,'error':'access_denied'})).headers['Location'],'/account')
    def test_cancel_clears_state(self):
        csrf=self.csrf()
        location=self.request('/login',{'action':'google_start','csrf':csrf}).headers['Location']
        state=parse_qs(urlsplit(location).query)['state'][0]
        self.assertEqual(self.request('/google-callback?'+urlencode({'state':state,'error':'access_denied'})).headers['Location'],'/login')
        self.assertEqual(self.request('/google-callback?'+urlencode({'state':state,'code':'fake'})).headers['Location'],'/login')

if __name__=='__main__': unittest.main()
