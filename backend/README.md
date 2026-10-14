# Santhi Cashew API

Flask REST API for the Santhi Cashew storefront. It uses MySQL, parameterized SQL queries, JWT authentication, and a pooled MySQL connection.

## Requirements

- Python 3.10 or newer
- MySQL 8.0.16 or newer (for enforced `CHECK` constraints)
- A MySQL account allowed to create/use the `santhi_cashew` database

## Setup

Run these commands from the repository root (`C:\website` in Windows PowerShell):

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS/Linux, activate the environment with:

```sh
source .venv/bin/activate
```

Initialize the database from the `backend` directory. Check that `mysql.exe` is installed and on `PATH` with `Get-Command mysql.exe`. These `cmd.exe` commands keep `<` redirection out of PowerShell, and MySQL will prompt for the account password:

```powershell
cmd.exe /c 'mysql.exe --user=root --password < schema.sql'
cmd.exe /c 'mysql.exe --user=root --password < seed.sql'
```

If you use another MySQL account, replace `root`. The account must be allowed to create/use `santhi_cashew`; `schema.sql` creates the database, and both scripts select it. If `mysql.exe` is not on `PATH`, use its full installation path in the commands. The seed uses an upsert keyed by product name; re-run it after changing seeded product prices or images to update existing products.

`JWT_SECRET_KEY` is the only variable the application explicitly requires at startup. To connect to MySQL, configure `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` as needed; their defaults are `127.0.0.1`, `3306`, `root`, an empty password, and `santhi_cashew`. `DB_POOL_SIZE` (default `5`) and `JWT_ACCESS_TOKEN_HOURS` (default `12`) are optional. `ADMIN_KEY` is optional and enables admin order-status updates by header when set; admin accounts can update statuses without it.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Generate a private JWT key in PowerShell and paste the output into `.env` as `JWT_SECRET_KEY`:

```powershell
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$bytes = New-Object byte[] 32
$rng.GetBytes($bytes)
[Convert]::ToBase64String($bytes)
$rng.Dispose()
```

Set `DB_PASSWORD` to the password for the MySQL user used above. Do not commit `.env`.

Start the API from the `backend` directory with:

```powershell
.\run.bat
```

The API binds to `127.0.0.1:5000`. The frontend's `js/api.js` targets `http://127.0.0.1:5000/api`. CORS allows the `null` origin used by `file://` pages and `http://127.0.0.1:5500`, `http://localhost:5500`, `http://127.0.0.1:5000`, and `http://localhost:5000`. It allows `GET`, `POST`, `PUT`, `DELETE`, and `OPTIONS`, with `Content-Type` and `Authorization` headers (plus `ADMIN_KEY` for the optional admin feature). This is intended for local development only.

Serve the frontend over HTTP from a second PowerShell window, opened in the repository root (`C:\website`):

```powershell
py -m http.server 5500 --bind 127.0.0.1
```

Then browse to `http://127.0.0.1:5500/` (or `http://localhost:5500/`).

Registration and login are available at `POST /api/register` and `POST /api/login`; the existing `/api/auth/register` and `/api/auth/login` paths remain supported. Registration expects JSON fields `name`, `mobile`, `email`, `password`, `address`, `city`, `pincode`, and `state`. Success returns JSON with status `201`; validation errors return `400` and duplicate mobile/email returns `409`.

## Example curl tests

Check that Flask is responding (Windows PowerShell):

```powershell
curl.exe http://localhost:5000/api/health
```

List products, search, and sort:

```powershell
curl.exe "http://localhost:5000/api/products?category=Raw&sort=lo"
curl.exe "http://localhost:5000/api/products?q=pepper&min_price=200&max_price=400"
```

Register a customer (save the returned token for authenticated requests):

```powershell
curl.exe -X POST http://localhost:5000/api/register -H "Content-Type: application/json" -d '{"name":"Asha Kumar","mobile":"9876543210","email":"asha@example.com","password":"cashews123","address":"12 Orchard Road","city":"Panruti","pincode":"607106","state":"Tamil Nadu"}'
```

Login with email or mobile:

```powershell
curl.exe -X POST http://localhost:5000/api/login -H "Content-Type: application/json" -d '{"identity":"asha@example.com","password":"cashews123"}'
```

Use the `token` returned by registration or login:

```powershell
curl.exe http://localhost:5000/api/auth/me -H "Authorization: Bearer YOUR_JWT"
```

Create an order. Product IDs are from the seeded database; prices and totals are recalculated by the server:

```powershell
curl.exe -X POST http://localhost:5000/api/orders -H "Content-Type: application/json" -H "Authorization: Bearer YOUR_JWT" -d '{"items":[{"product_id":1,"size":"250 g","qty":2}],"shipping":{"name":"Asha Kumar","mobile":"9876543210","address":"12 Orchard Road","city":"Panruti","pincode":"607106","state":"Tamil Nadu"},"payment_method":"COD"}'
```

Read the signed-in customer's orders or quote a cart using current database prices:

```powershell
curl.exe http://localhost:5000/api/orders -H "Authorization: Bearer YOUR_JWT"
curl.exe -X POST http://localhost:5000/api/cart/quote -H "Content-Type: application/json" -d '{"items":[{"product_id":1,"size":"250 g","qty":2}]}'
```

Subscribe to the newsletter (repeated subscriptions are harmless):

```powershell
curl.exe -X POST http://localhost:5000/api/newsletter -H "Content-Type: application/json" -d '{"email":"asha@example.com"}'
```

Advance an order one tracking stage at a time using the administrator key configured in `.env`:

```powershell
curl.exe -X PUT http://localhost:5000/api/orders/SC1234567/status -H "Content-Type: application/json" -H "ADMIN_KEY: YOUR_ADMIN_KEY" -d '{"status":"Packed"}'
```

Cancel an order that is still Placed or Packed:

```powershell
curl.exe -X PUT http://localhost:5000/api/orders/SC1234567/cancel -H "Authorization: Bearer YOUR_JWT"
```
