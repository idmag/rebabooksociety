# Reba Book Society

A PHP storefront for Reba Book Society, featuring the supplied cover artwork, a searchable catalogue, cart, customer accounts and order requests.

## Run locally

Requires PHP 8.1 or newer. The entry point and assets are at the repository root; configure the web server to serve this directory, or run from the repository root:

```sh
php -S 0.0.0.0:8000 -t .
```

Visit http://localhost:8000. Use a web server configured to execute PHP; opening `index.php` directly in a browser will not work.

### Private customer storage

Customer accounts and orders are stored in `data.json` in a **private directory outside the web server's entire document root**. By default, this is the sibling directory `reba-book-society-data` next to the website directory. The PHP process must be able to create and write to it. If that location is inside your server's document root, or is not writable, set the `REBA_STORAGE_DIR` environment variable to an absolute path to a writable, private directory outside the document root. The application refuses to use a storage path inside the document root. Set directory permissions so only the PHP service account can access it; the data file is created with restrictive permissions. Back it up securely and do not commit it to Git.

**Upgrading from the previous `public/` layout:** Before making the repository root web-accessible, stop the server and move the existing `storage/data.json` to the new private directory (or the directory specified by `REBA_STORAGE_DIR`). Preserve its ownership and restrictive permissions. Do not leave a copy in the website directory. The application refuses to use a new data store while the old file is present, to avoid silently losing access to existing accounts and orders. The included `storage/.htaccess` is only an extra Apache safeguard; it does not protect other web servers or the PHP development server. Verify that your server cannot serve the private data directory or `.git` metadata. Do not deploy the `.git` directory under a web root; configure equivalent access restrictions for non-Apache servers.

Use HTTPS in production. PHP sessions must be configured to use a private server-side session directory. Passwords are stored using PHP's `password_hash` and checked using `password_verify`; they are never stored as plain text.

## Before going live

The catalogue prices are illustrative starter prices and should be verified in `index.php`. Checkout records an order request, not a paid or fulfilled order. No payment gateway, shipping calculation, notification, inventory management or admin dashboard is configured. An operator must securely review the server-side order records and arrange confirmation, delivery and payment separately. Add contact details and a precise shop address after confirming them. For a production deployment, use HTTPS, a proper transactional database and backups, operational monitoring, a privacy policy, and a secure administrative order workflow. The included basic login throttling is not a substitute for infrastructure-level rate limiting.
