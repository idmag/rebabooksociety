# Reba Book Society

A PHP storefront for Reba Book Society, featuring the supplied cover artwork, a searchable catalogue, wishlist, cart, customer accounts and order requests.

## Run locally

Requires PHP 8.1 or newer. The entry point and assets are at the repository root; configure the web server to serve this directory, or run from the repository root:

```sh
php -S 0.0.0.0:8000 -t . router.php
```

Visit http://localhost:8000/. The development router serves the clean URLs and only exposes storefront assets. Use a web server configured to execute PHP; opening `index.php` directly in a browser will not work.

### Clean URLs in production

Apache needs `mod_rewrite` enabled and `AllowOverride All` (or the equivalent rewrite and access rules in the virtual host) so the included `.htaccess` can route paths such as `/shop`, `/about`, `/contact`, `/book/perseus`, `/cart`, `/wishlist`, and `/account` to `index.php`. The homepage is at `/`; old `/home` and `?page=...` bookmarks redirect to the clean paths. Search and the multi-select category filters use query parameters; older single-category links remain supported.

For Nginx, configure the normal PHP-FPM handler and route non-file requests to the front controller, for example:

```nginx
location / { try_files $uri $uri/ /index.php?$query_string; }
location ~ /\. { deny all; }
location ^~ /storage/ { deny all; }
location ^~ /tests/ { deny all; }
location = /router.php { deny all; }
```

If the site is installed in a subdirectory, adjust the Nginx front-controller path to include that subdirectory. Do not serve repository metadata, `router.php`, `tests/`, or the legacy `storage/` directory in production. The contact page lists the supplied mobile / WhatsApp number and shop address.

### Private customer storage

Customer accounts and orders are stored in `data.json` in a **private directory outside the web server's entire document root**. By default, this is the sibling directory `reba-book-society-data` next to the website directory. The PHP process must be able to create and write to it. If that location is inside your server's document root, or is not writable, set the `REBA_STORAGE_DIR` environment variable to an absolute path to a writable, private directory outside the document root. The application refuses to use a storage path inside the document root. Set directory permissions so only the PHP service account can access it; the data file is created with restrictive permissions. Back it up securely and do not commit it to Git.

**Upgrading from the previous `public/` layout:** Before making the repository root web-accessible, stop the server and move the existing `storage/data.json` to the new private directory (or the directory specified by `REBA_STORAGE_DIR`). Preserve its ownership and restrictive permissions. Do not leave a copy in the website directory. The application refuses to use a new data store while the old file is present, to avoid silently losing access to existing accounts and orders. The included `storage/.htaccess` is only an extra Apache safeguard; it does not protect other web servers or the PHP development server. Verify that your server cannot serve the private data directory or `.git` metadata. Do not deploy the `.git` directory under a web root; configure equivalent access restrictions for non-Apache servers.

Use HTTPS in production. PHP sessions must be configured to use a private server-side session directory. Passwords are stored using PHP's `password_hash` and checked using `password_verify`; they are never stored as plain text.

### Wishlists

Customers can save books using the heart buttons and review or remove them at `/wishlist`. A guest wishlist is kept in their browser session; signing in or registering merges it into their account so it persists across devices. Signed-in wishlists are stored with the account in the private data file. Books removed from the shop are hidden from the wishlist until restored; out-of-stock books can still be saved. Wishlist data is not shared between accounts.

### Account settings and password recovery

Signed-in customers can update their display name and their saved delivery and billing addresses under `/account`. Their saved delivery address is offered at checkout; changing it does not alter past orders. Password changes require the current password and invalidate other active sessions. Passwords must be at least six characters; longer, unique passwords are recommended. Existing account records work without migration.

Recovery emails use PHP `mail()` and the From address `info@rebabooksociety.websolve.co.in`. On the exact live host `rebabooksociety.websolve.co.in`, reset links default to `https://rebabooksociety.websolve.co.in`. The host must be configured to deliver PHP mail and authorise that sender; set up domain authentication (SPF, DKIM and DMARC as appropriate) and monitor delivery. **Send a real test email and complete a reset on the deployed site before relying on recovery.**

For another domain or an installation in a subdirectory, explicitly set `REBA_BASE_URL` in the hosting panel, Apache configuration or PHP-FPM environment, for example:

```text
REBA_BASE_URL=https://your-domain.example/subdirectory
```

It must be the actual HTTPS site URL, without a trailing slash, query string, or fragment. Without an explicit URL, recovery is disabled on other hosts, including the local preview. A configured URL and sender do not prove that the host can deliver mail; failures are logged by the server. Configure the live site and PHP session cookies for HTTPS only. Set proxy/edge and web-server access logs to omit query strings on `/reset-password`, since the initial recovery link contains a secret token; do not log reset email bodies or tokens. Tokens are stored only as hashes, expire after 30 minutes, can be used once, and are invalidated by a password change. Recovery requests are rate-limited and use the same response whether or not an account exists. These application limits are not a substitute for server-level rate limiting.

The isolated account integration test can be run with `python3 tests/account_flow.py` (set `PHP_BIN` if PHP is not on your PATH). It uses a temporary private data file and disables actual mail delivery; it does not verify your server’s email transport.

### Administrator and inventory

The administrator is `ahmadmdujan@gmail.com`. Registration alone does **not** grant privileges: registration currently does not verify email addresses, so assigning admin rights by email alone would allow impersonation. After deployment, the mailbox owner should register or use their existing account, use **Forgot your password?** with that address, follow the email link, set a new password, and sign in. Successfully completing that email-based reset verifies control of the mailbox and activates admin access. It also invalidates any previously active sessions. Email recovery must be operational as described above; no admin password is embedded in the site.

Once activated, **Manage inventory** appears on the account page and opens `/admin`. Only the verified admin can access it or make changes. The admin can update the whole-rupee MRP, selling price and available quantities, remove a book from the public shop, and restore it later. Existing quantities start as **untracked** (blank), not zero; set actual counts before relying on stock controls. Tracked quantities are reduced atomically when an order request is submitted, even though payment is not taken. There is no automatic cancellation or restock workflow; the operator must restore the quantity manually if an order request is cancelled. Hidden products remain in existing order histories. This dashboard does not yet add new titles or upload covers; add those through the catalogue code.

The catalogue is persisted in the same private data file as accounts and orders. Starter catalogue entries are added when missing, but editing starter metadata or prices in `index.php` after the first run does not overwrite saved inventory. Existing saved prices initially serve as both MRP and selling price until the administrator updates them; discounts are calculated from those values. Change existing prices in the admin dashboard and back up the private data file. Do not replace it during deployment.

## Before going live

The catalogue prices are illustrative starter prices and should be verified in the admin dashboard. Checkout records an order request, not a paid or fulfilled order. No payment gateway, shipping calculation, order notification or administrative order workflow is configured. An operator must securely review the server-side order records and arrange confirmation, delivery and payment separately. For a production deployment, use HTTPS, a proper transactional database and backups, operational monitoring, a privacy policy, and a secure administrative order workflow. The included basic login throttling is not a substitute for infrastructure-level rate limiting.

### Deploying visual updates

Deploy `index.php` and the entire `assets/` directory together, including `storefront.css`, `college-street.jpg`, and the logo files. The stylesheet URL includes a content-based version to prevent browsers from reusing an older design with newer page markup. If a CDN or reverse proxy caches HTML, purge that cache after deploying; make sure the server actually serves the current files.
