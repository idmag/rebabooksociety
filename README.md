# Reba Book Society

A PHP storefront for Reba Book Society, featuring the supplied cover artwork, a searchable catalogue, cart, customer accounts and order requests.

## Run locally

Requires PHP 8.1 or newer. From the repository root:

```sh
php -S 0.0.0.0:8000 -t public
```

Visit http://localhost:8000. The `storage` directory must be writable by PHP. Customer accounts and orders are stored in `storage/data.json`, outside the `public` document root. The file is created with restrictive permissions and excluded from Git. **Always configure your web server's document root as `public/`**, never the repository root. Use HTTPS in production and back up the storage directory securely. PHP sessions must be configured to use a private server-side session directory. Passwords are stored using PHP's `password_hash` and checked using `password_verify`; they are never stored as plain text.

## Before going live

The catalogue prices are illustrative starter prices and should be verified in `public/index.php`. Checkout records an order request, not a paid or fulfilled order. No payment gateway, shipping calculation, notification, inventory management or admin dashboard is configured. An operator must securely review the server-side order records and arrange confirmation, delivery and payment separately. Add contact details and a precise shop address after confirming them. For a production deployment, use HTTPS, a proper transactional database and backups, operational monitoring, a privacy policy, and a secure administrative order workflow. The included basic login throttling is not a substitute for infrastructure-level rate limiting.
