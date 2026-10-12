# Santhi Cashew

The storefront is served by a Python Flask API and MySQL. The backend uses `mysql-connector-python` connection pooling, Flask-CORS, PyJWT, `python-dotenv`, `requests`, and Werkzeug password hashing. The image routes serve the uploaded logo and cashew photo from `static/images/`.

## Setup on Windows

1. Install and start MySQL Server. The MySQL account must be allowed to create the configured database and tables.
2. Create a private environment file from the template and edit it with your MySQL credentials and a new, random JWT secret:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Set `SANTHI_DB_HOST`, `SANTHI_DB_PORT`, `SANTHI_DB_USER`, `SANTHI_DB_PASSWORD`, and `SANTHI_DB_NAME`. Set `JWT_SECRET` to a random secret of at least 32 characters. `ADMIN_EMAIL` and `ADMIN_PASSWORD` are optional; they are only needed when creating a new admin account. Razorpay credentials are optional and only needed for online payments; COD works without them.

3. Install the Python dependencies and initialize the schema and catalog:

   ```powershell
   python -m pip install -r requirements.txt
   python seed.py
   ```

4. Start the API:

   ```powershell
   python server.py
   ```

5. Open the storefront with VS Code Live Server at `http://127.0.0.1:5500` or `http://localhost:5500`.

Check the API using `http://127.0.0.1:5000/api/health` and `http://127.0.0.1:5000/api/products`. `seed.py` creates missing database tables without dropping existing data. It inserts the six catalog products and their pack prices only when the products table is empty; it never resets existing stock or deletes users or orders. Legacy password hashes are upgraded after a successful login. `.env` is excluded from source control.

## API overview

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/products`, `GET /api/products/<id>`
- `POST /api/orders`, `GET /api/orders`, `GET /api/orders/<id>`, `PATCH /api/orders/<id>/cancel`
- `POST /api/payments/verify`
- Administrator: `GET /api/admin/orders`, `PATCH /api/admin/orders/<id>/status`, `GET/POST /api/admin/products`, `PUT/DELETE /api/admin/products/<id>`
- `GET /api/health`, `GET /images/<file>`

The order API reads pack prices from MySQL, checks stock and writes orders in transactions. Never put `.env` in source control. Use HTTPS and restrict MySQL privileges before deploying publicly. Card details are collected only by Razorpay Checkout and are never sent to or stored by this application.
