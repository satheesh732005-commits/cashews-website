# Santhi Cashew API

Flask REST API for the Santhi Cashew storefront. It uses MySQL, parameterized SQL queries, JWT authentication, and a pooled MySQL connection.

## Requirements

- Python 3.10 or newer
- MySQL 8.0 or newer
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

Initialize the database from the `backend` directory. These commands use `cmd.exe` so MySQL's input redirection works from Windows PowerShell:

```powershell
cmd /c "mysql -u root -p < schema.sql"
cmd /c "mysql -u root -p santhi_cashew < seed.sql"
```

The seed uses an upsert keyed by product name. Re-run the second command after changing seeded product prices or images to update existing products.

Copy `.env.example` to `.env`, then set the MySQL password, a long random `JWT_SECRET_KEY`, and (optionally) a private `ADMIN_KEY`.

```powershell
Copy-Item .env.example .env
```

Start the API from the `backend` directory:

```sh
python app.py
```

The API listens on `http://localhost:5000`. CORS is enabled for `http://127.0.0.1:5500` and `http://localhost:5500`.

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
curl.exe -X POST http://localhost:5000/api/auth/register -H "Content-Type: application/json" -d '{"name":"Asha Kumar","mobile":"9876543210","email":"asha@example.com","password":"cashews123","address":"12 Orchard Road","city":"Panruti","pincode":"607106","state":"Tamil Nadu"}'
```

Login with email or mobile:

```powershell
curl.exe -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"identity":"asha@example.com","password":"cashews123"}'
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
