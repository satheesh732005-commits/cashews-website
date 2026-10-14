"use strict";

const API_BASE_URL = "http://127.0.0.1:5000/api";
const TOKEN_KEY = "sc_token";
const USER_KEY = "sc_user";

function saveAuth(payload) {
  const token = payload.token || payload.access_token || payload.data?.token;
  if (!token) throw new Error("The server did not return a login token.");
  localStorage.setItem(TOKEN_KEY, token);
  const user = payload.user || payload.data?.user || null;
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  return { ...payload, token, user };
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

async function request(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch (error) {
    if (error instanceof TypeError) {
      console.error("Santhi Cashew API network request failed:", error);
      throw new Error(`Can't reach the Santhi Cashew server at ${API_BASE_URL}. Check that Flask is running and the frontend origin is allowed by CORS.`, { cause: error });
    }
    throw error;
  }

  let payload = {};
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    payload = await response.json();
  } else if (!response.ok) {
    payload = { error: `Request failed (${response.status}).` };
  }
  if (!response.ok) {
    if (response.status === 401 && token) {
      clearAuth();
      window.dispatchEvent(new Event("sc-auth-changed"));
    }
    throw new Error(payload.error || payload.message || `Request failed (${response.status}).`);
  }
  return payload;
}

async function getProducts(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim()) params.set(key, value);
  });
  const query = params.toString();
  const payload = await request(`/products${query ? `?${query}` : ""}`);
  return Array.isArray(payload) ? payload : (payload.products || payload.data || []);
}

async function register(details) {
  return saveAuth(await request("/auth/register", {
    method: "POST",
    body: JSON.stringify(details)
  }));
}

async function login(credentials) {
  return saveAuth(await request("/auth/login", {
    method: "POST",
    body: JSON.stringify(credentials)
  }));
}

async function getProfile() {
  const payload = await request("/auth/me");
  const user = payload.user || payload.profile || payload;
  if (user && typeof user === "object") localStorage.setItem(USER_KEY, JSON.stringify(user));
  return user;
}

async function placeOrder(order) {
  return request("/orders", { method: "POST", body: JSON.stringify(order) });
}

async function getMyOrders() {
  const payload = await request("/orders");
  return Array.isArray(payload) ? payload : (payload.orders || payload.data || []);
}

async function cancelOrder(orderCode) {
  return request(`/orders/${encodeURIComponent(orderCode)}/cancel`, { method: "PUT" });
}

async function updateOrderStatus(orderCode, status) {
  return request(`/orders/${encodeURIComponent(orderCode)}/status`, {
    method: "PUT",
    body: JSON.stringify({ status })
  });
}

async function subscribeNewsletter(email) {
  return request("/newsletter", {
    method: "POST",
    body: JSON.stringify({ email })
  });
}
