"""OAuth initiation and state tests with synthetic credentials; no Google network calls.
Run: PHP_BIN=/path/to/php python3 tests/google_oauth_flow.py
"""
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
    def test_auth_ui_keeps_checkout_and_google_actions(self):
        page=self.request('/login?next=checkout').read().decode()
        self.assertIn('class="auth-shell"',page)
        self.assertIn('aria-current="page"',page)
        self.assertIn('Continue with Google',page)
        self.assertIn('name="action" value="google_start"',page)
        self.assertEqual(page.count('name="next" value="checkout"'),2)
        self.assertIn('/register?next=checkout',page)
        self.assertIn('href="/forgot-password"',page)
        register=self.request('/register?next=checkout').read().decode()
        self.assertIn('name="action" value="register"',register)
        self.assertIn('name="name"',register)
        self.assertIn('Minimum 6 Characters',register)
        self.assertIn('/login?next=checkout',register)

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

class PrivateConfigFlow(unittest.TestCase):
    def test_private_file_enables_sign_in_and_bad_files_do_not(self):
        with tempfile.TemporaryDirectory(prefix='reba-oauth-private-') as tmp:
            private=Path(tmp)/'private'; private.mkdir(mode=0o700)
            config=private/'google-config.json'
            config.write_text(json.dumps({'base_url':'https://example.test','client_id':'12345-example.apps.googleusercontent.com','client_secret':'private-test-secret'}))
            config.chmod(0o600)
            # A path within a document root must never supply secrets.
            code='require "google-oauth.php"; $_SERVER["DOCUMENT_ROOT"]=$argv[1]; putenv("REBA_STORAGE_DIR=".$argv[2]); echo googlePrivateConfig() ? "unsafe" : "blocked";'
            result=subprocess.run([os.environ.get('PHP_BIN','php'),'-r',code,tmp,str(private)],cwd=ROOT,capture_output=True,text=True,check=True)
            self.assertEqual(result.stdout,'blocked')
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
            env=os.environ.copy()
            for key in ('REBA_BASE_URL','REBA_GOOGLE_CLIENT_ID','REBA_GOOGLE_CLIENT_SECRET'): env.pop(key,None)
            env['REBA_STORAGE_DIR']=str(private)
            with open(Path(tmp)/'log','w+') as log:
                server=subprocess.Popen([env.get('PHP_BIN','php'),'-S',f'127.0.0.1:{port}','-t','.','router.php'],cwd=ROOT,env=env,stdout=log,stderr=log)
                base=f'http://127.0.0.1:{port}'
                client=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()),NoRedirect())
                deadline=time.monotonic()+20
                try:
                    while True:
                        try:
                            page=client.open(base+'/login',timeout=1).read().decode(); break
                        except (OSError,URLError):
                            if server.poll() is not None or time.monotonic()>deadline: raise RuntimeError('Server failed to start')
                            time.sleep(.05)
                    self.assertIn('Continue with Google',page)
                    self.assertNotIn('private-test-secret',page)
                    token=re.search(r'name="csrf" value="([^"]+)',page).group(1)
                    try:
                        client.open(Request(base+'/login',urlencode({'csrf':token,'action':'google_start'}).encode()))
                    except HTTPError as response:
                        self.assertEqual(response.code,302)
                        query=parse_qs(urlsplit(response.headers['Location']).query)
                        self.assertEqual(query['redirect_uri'],['https://example.test/google-callback'])
                        self.assertNotIn('private-test-secret',response.headers['Location'])
                        response.close()
                    config.write_text('{broken')
                    self.assertNotIn('Continue with Google',client.open(base+'/login').read().decode())
                    config.unlink()
                    target=private/'other.json'
                    target.write_text(json.dumps({'base_url':'https://example.test','client_id':'12345-example.apps.googleusercontent.com','client_secret':'private-test-secret'}))
                    config.symlink_to(target)
                    self.assertNotIn('Continue with Google',client.open(base+'/login').read().decode())
                finally:
                    server.terminate(); server.wait(timeout=10)

if __name__=='__main__': unittest.main()
