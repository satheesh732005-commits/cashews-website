"use strict";

const LOCAL_PRODUCTS = [
  { id: "w320-whole", name: "Whole Cashew W320", category: "Raw", grade: "W320", prices: { "250 g": 229, "500 g": 550, "1 kg": 900 }, stock: 120, rating: 4.8, reviews: 128, description: "Creamy, naturally sweet whole kernels, hand graded for an everyday premium snack." },
  { id: "w180-jumbo", name: "Premium Jumbo W180", category: "Raw", grade: "W180", prices: { "250 g": 299, "500 g": 400, "1 kg": 750 }, stock: 40, rating: 4.9, reviews: 84, description: "Our show-stopping jumbo kernels: exceptionally large, delicate and buttery." },
  { id: "roasted-salted", name: "Roasted Salted", category: "Roasted", grade: "W240", prices: { "250 g": 269, "500 g": 600, "1 kg": 950 }, stock: 8, rating: 4.7, reviews: 96, description: "Gently roasted for a warm crunch and finished with just a pinch of salt." },
  { id: "pepper-masala", name: "Pepper Masala", category: "Flavoured", grade: "W320", prices: { "250 g": 279, "500 g": 550, "1 kg": 900 }, stock: 60, rating: 4.8, reviews: 51, description: "A lively South Indian pepper masala coating meets a crisp, roasted cashew." },
  { id: "cashew-pieces", name: "Cashew Pieces", category: "Raw", grade: "Broken", prices: { "250 g": 179, "500 g": 340, "1 kg": 660 }, stock: 200, rating: 4.6, reviews: 73, description: "Fresh, creamy cashew pieces ready for payasam, baking, curries and cooking." },
  { id: "festive-gift-box", name: "Festive Gift Box", category: "Gift", grade: "W240", prices: { "250 g": 399, "500 g": 600, "1 kg": 950 }, stock: 0, rating: 4.9, reviews: 32, description: "A thoughtful gift, beautifully packed with a selection of our finest cashews." }
];

const PACKS = ["250 g", "500 g", "1 kg"];
const STATES = ["Andhra Pradesh", "Karnataka", "Kerala", "Maharashtra", "Puducherry", "Tamil Nadu", "Telangana", "Other"];
const CART_KEY = "sc_cart";
let products = LOCAL_PRODUCTS.map(product => ({ ...product }));
let cart = readCart();
let userProfile = null;
let productModalReturn = null;
let lastOrder = null;
let shopFilters = { category: "", query: "", grade: "", price: "", sort: "featured" };
let revealObserver = null;
let productApiAvailable = true;
let shopRequestNumber = 0;

function readCart() {
  try {
    const parsed = JSON.parse(localStorage.getItem(CART_KEY) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persistCart() {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
  updateCartCount(true);
}

function money(amount) {
  return `₹${Number(amount || 0).toLocaleString("en-IN")}`;
}

function safe(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

function routeInfo() {
  const hash = location.hash || "#/";
  const [path, query = ""] = hash.slice(1).split("?");
  return { path: path || "/", params: new URLSearchParams(query) };
}

function productId(product) {
  return String(product.id ?? product._id ?? product.slug ?? product.name);
}

function getProduct(id) {
  return products.find(product => productId(product) === String(id));
}

function formatCategory(category) {
  return String(category || "").toLowerCase() === "gift" ? "Gift" : (category || "Raw");
}

function productImage(product) {
  const visual = String(product.category || "").toLowerCase();
  const altText = `${product.name} cashews`;
  return `<img src="assets/cashew-product.png" alt="${safe(altText)}" data-category="${safe(visual)}" loading="lazy">`;
}

function firstPackPrice(product) {
  const prices = product.prices || product.price || {};
  return Number(prices["250 g"] ?? prices["250g"] ?? prices["250"] ?? product.price_250 ?? product.price250 ?? product.price ?? 0);
}

function priceFor(product, pack) {
  const prices = product.prices || product.price || {};
  const fallbackKeys = { "250 g": ["250g", "250"], "500 g": ["500g", "500"], "1 kg": ["1kg", "1000g", "1000"] };
  const dbKeys = { "250 g":"price_250", "500 g":"price_500", "1 kg":"price_1kg" };
  const price = prices[pack] ?? fallbackKeys[pack].map(key => prices[key]).find(value => value != null) ?? product[dbKeys[pack]];
  if (price != null) return Number(price);
  const base = firstPackPrice(product);
  return Math.round(base * ({ "250 g": 1, "500 g": 1.94, "1 kg": 3.78 }[pack]));
}

function stockOf(product) {
  return Math.max(0, Number(product.stock ?? product.stockQuantity ?? 0));
}

function updateCartCount(pop = false) {
  const count = cart.reduce((sum, item) => sum + item.quantity, 0);
  const badge = document.getElementById("cart-count");
  if (!badge) return;
  badge.textContent = count;
  badge.setAttribute("aria-label", `${count} items in cart`);
  if (pop) {
    badge.classList.remove("pop");
    requestAnimationFrame(() => badge.classList.add("pop"));
  }
}

function toast(message, isError = false) {
  const region = document.getElementById("toast-region");
  const item = document.createElement("div");
  item.className = `toast${isError ? " error" : ""}`;
  item.setAttribute("role", isError ? "alert" : "status");
  item.textContent = message;
  region.append(item);
  window.setTimeout(() => item.remove(), 3600);
}

function renderAuthLinks() {
  const token = localStorage.getItem("sc_token");
  const user = userProfile || getStoredUser();
  const loginLink = document.getElementById("login-link");
  const registerLink = document.getElementById("register-link");
  const greeting = document.getElementById("user-greeting");
  const logoutButton = document.getElementById("logout-button");
  if (!loginLink || !registerLink || !greeting || !logoutButton) return;
  loginLink.hidden = Boolean(token);
  registerLink.hidden = Boolean(token);
  greeting.hidden = !token;
  greeting.textContent = token ? `Hi, ${user?.name || "there"}` : "";
  logoutButton.hidden = !token;
}

function showServerError(form, error) {
  const message = error instanceof Error ? error.message : "Something went wrong. Please try again.";
  const output = form.querySelector(".form-server-error");
  if (output) {
    output.textContent = message;
    output.hidden = false;
  }
  toast(message, true);
}

function clearServerError(form) {
  const output = form.querySelector(".form-server-error");
  if (output) {
    output.textContent = "";
    output.hidden = true;
  }
}

function productCard(product) {
  const id = productId(product);
  const stock = stockOf(product);
  const price = firstPackPrice(product);
  const mrp = Math.round(price / .85);
  const stockLabel = stock === 0 ? "Out of stock" : stock < 10 ? `Only ${stock} left` : "In stock";
  const stockClass = stock === 0 ? "out" : stock < 10 ? "low" : "";
  return `<article class="product-card tilt-card" data-product="${safe(id)}">
    <button class="product-open" type="button" data-open-product="${safe(id)}" aria-label="View ${safe(product.name)}"></button>
    <div class="product-visual"><span class="product-badge">${safe(formatCategory(product.category))} · ${safe(product.grade || "W320")}</span>${productImage(product)}<span class="stock-badge ${stockClass}">${stockLabel}</span></div>
    <div class="product-info"><div class="rating" aria-label="${safe(product.rating || 4.8)} out of 5 stars">★★★★★ <span>${safe(product.rating || "4.8")} (${safe(product.reviews || 0)})</span></div>
    <h3>${safe(product.name)}</h3><div class="product-meta">Hand-graded · vacuum packed</div>
    <div class="price-line"><strong>${money(price)}</strong><s>${money(mrp)}</s><span class="discount">15% off</span></div>
    <p class="delivery-note">FREE delivery above ₹999</p>
    <button class="button small quick-add" type="button" data-quick-add="${safe(id)}" ${stock === 0 ? "disabled" : ""} aria-label="Add ${safe(product.name)} 250 gram pack to cart">Add to cart</button></div>
  </article>`;
}

function productGrid(items, emptyText = "No cashews match those filters. Try changing your search.") {
  if (!items.length) return `<div class="empty-products"><p>${safe(emptyText)}</p><button class="button ghost small" type="button" data-reset-filters>Clear filters</button></div>`;
  return `<div class="product-grid">${items.map(productCard).join("")}</div>`;
}

function renderHome() {
  const bestsellers = products.slice(0, 4);
  return `<div class="page-enter">
    <section class="hero"><div class="wrap hero-grid">
      <div><span class="eyebrow">From Panruti, with care</span><h1>Crunch into <em>pure, creamy</em> cashews</h1>
        <p class="hero-copy">Hand-graded kernels from the orchards of Tamil Nadu, vacuum packed the day they are roasted.</p>
        <div class="hero-actions"><a class="button" href="#/shop">Shop Now <span aria-hidden="true">→</span></a><a class="button alt" href="#/register">Join Us</a></div>
      </div>
      <div class="hero-stage" aria-label="A bowl of premium cashews">
        <div class="hero-image-shell" id="hero-parallax"><img src="assets/cashew-product.png" alt="Fresh, creamy Panruti cashews"></div>
        <div class="hero-note note-one">100% carefully graded<span>From Tamil Nadu</span></div><div class="hero-note note-two">Packed fresh<span>Sealed for the crunch</span></div><div class="hero-stamp">PANRUTI<br>HARVEST<br>✦</div>
      </div>
    </div></section>
    <section class="section tight"><div class="wrap feature-strip">
      <div class="feature reveal"><span class="feature-icon">✦</span><strong>Premium grade W180 to W320</strong><p>Hand-selected kernels, every time.</p></div>
      <div class="feature reveal"><span class="feature-icon">♧</span><strong>Free delivery above ₹999</strong><p>Good things delivered to your door.</p></div>
      <div class="feature reveal"><span class="feature-icon">▣</span><strong>Secure payment</strong><p>UPI, cards and net banking.</p></div>
      <div class="feature reveal"><span class="feature-icon">◉</span><strong>Fresh vacuum pack</strong><p>Locks in freshness and flavour.</p></div>
    </div></section>
    <section class="section"><div class="wrap"><div class="section-heading"><div><span class="eyebrow">Find your favourite</span><h2>Shop by category</h2></div></div>
      <div class="category-tiles">${[
        ["Raw", "Pure & creamy", "Raw"], ["Roasted", "Golden, crisp bites", "Roasted"], ["Flavoured", "A little extra spice", "Flavoured"], ["Gift boxes", "Give a little goodness", "Gift"]
      ].map(([name, desc, key]) => `<a class="category-tile reveal" href="#/shop?category=${encodeURIComponent(key)}"><img src="assets/cashew-product.png" alt="" loading="lazy"><strong>${name}</strong><span>${desc} →</span></a>`).join("")}</div>
    </div></section>
    <section class="section tight"><div class="wrap"><div class="section-heading"><div><span class="eyebrow">Loved in every home</span><h2>Bestsellers</h2></div><a class="text-button" href="#/shop">Shop all cashews →</a></div>${productGrid(bestsellers)}</div></section>
    <section class="section"><div class="wrap"><div class="section-heading"><div><span class="eyebrow">Kind words, shared</span><h2>A little love from our customers</h2></div></div>
      <div class="feature-strip"><blockquote class="feature reveal"><div class="rating">★★★★★</div><p>“The jumbo cashews are deliciously creamy. You can taste the freshness.”</p><strong>— Meera R.</strong></blockquote>
      <blockquote class="feature reveal"><div class="rating">★★★★★</div><p>“Beautifully packed and delivered quickly. The pepper masala is a favourite.”</p><strong>— Arjun K.</strong></blockquote>
      <blockquote class="feature reveal"><div class="rating">★★★★★</div><p>“The quality is lovely, and the gift box made a perfect festive surprise.”</p><strong>— Divya S.</strong></blockquote></div>
    </div></section>
    <section class="section tight"><div class="wrap newsletter"><div><h2>A fresh little note from us</h2><p>New harvests, good recipes and a little crunch in your inbox.</p></div><form id="newsletter-form" class="newsletter-form"><label class="sr-only" for="newsletter-email">Email address</label><input id="newsletter-email" name="email" type="email" placeholder="Your email address" required><button class="button" type="submit">Subscribe</button></form></div></section>
  </div>`;
}

function getShopProducts() {
  const query = shopFilters.query.toLowerCase().trim();
  let result = products.filter(product => {
    const categoryMatch = !shopFilters.category || formatCategory(product.category).toLowerCase() === shopFilters.category.toLowerCase();
    const queryMatch = !query || `${product.name} ${product.category} ${product.grade}`.toLowerCase().includes(query);
    const gradeMatch = !shopFilters.grade || String(product.grade).toUpperCase() === shopFilters.grade.toUpperCase();
    const price = firstPackPrice(product);
    const priceMatch = !shopFilters.price || (shopFilters.price === "under" && price < 250) || (shopFilters.price === "mid" && price >= 250 && price <= 300) || (shopFilters.price === "over" && price > 300);
    return categoryMatch && queryMatch && gradeMatch && priceMatch;
  });
  if (shopFilters.sort === "low") result.sort((a, b) => firstPackPrice(a) - firstPackPrice(b));
  if (shopFilters.sort === "high") result.sort((a, b) => firstPackPrice(b) - firstPackPrice(a));
  if (shopFilters.sort === "name") result.sort((a, b) => a.name.localeCompare(b.name));
  return result;
}

function renderShop() {
  const items = getShopProducts();
  const categoryChips = ["All", "Raw", "Roasted", "Flavoured", "Gift"];
  return `<div class="page-enter"><section class="section"><div class="wrap">
    <div class="section-heading"><div><span class="eyebrow">Straight from Panruti</span><h1>Shop cashews</h1></div><p id="shop-count">${items.length} delicious ${items.length === 1 ? "choice" : "choices"}</p></div>
    <div class="chips" aria-label="Filter by category">${categoryChips.map(category => `<button class="chip ${shopFilters.category.toLowerCase() === (category === "All" ? "" : category.toLowerCase()) ? "active" : ""}" type="button" data-category-chip="${category === "All" ? "" : category}">${category}</button>`).join("")}</div>
    <div class="shop-layout"><aside class="filter-panel"><h3>Find your perfect pack</h3><div class="filter-content">
      <div class="filter-group"><strong>Grade</strong>${[["","All grades"],["W180","W180 Jumbo"],["W240","W240"],["W320","W320"],["Broken","Broken"]].map(([value,label]) => `<label class="filter-option"><input type="radio" name="grade" value="${value}" ${shopFilters.grade === value ? "checked" : ""}> ${label}</label>`).join("")}</div>
      <div class="filter-group"><strong>Price for 250 g</strong>${[["","Any price"],["under","Under ₹250"],["mid","₹250–₹300"],["over","Over ₹300"]].map(([value,label]) => `<label class="filter-option"><input type="radio" name="price" value="${value}" ${shopFilters.price === value ? "checked" : ""}> ${label}</label>`).join("")}</div>
    </div></aside>
    <div><div class="shop-tools"><label class="sr-only" for="shop-search">Search products</label><input id="shop-search" class="field-control shop-search" type="search" value="${safe(shopFilters.query)}" placeholder="Search the collection..."><label class="sr-only" for="sort-products">Sort products</label><select id="sort-products" class="field-control" style="max-width:190px"><option value="featured" ${shopFilters.sort === "featured" ? "selected" : ""}>Featured</option><option value="low" ${shopFilters.sort === "low" ? "selected" : ""}>Price low → high</option><option value="high" ${shopFilters.sort === "high" ? "selected" : ""}>Price high → low</option><option value="name" ${shopFilters.sort === "name" ? "selected" : ""}>Name A → Z</option></select></div>
    <div id="shop-results">${productGrid(items)}</div></div></div>
  </div></section></div>`;
}

function cartSubtotal() {
  return cart.reduce((sum, item) => {
    const product = getProduct(item.productId);
    return sum + (product ? priceFor(product, item.pack) * item.quantity : 0);
  }, 0);
}

function deliveryCost(subtotal) {
  return subtotal === 0 || subtotal >= 999 ? 0 : 60;
}

function renderSummary(includeButton = true) {
  const subtotal = cartSubtotal();
  const delivery = deliveryCost(subtotal);
  const more = Math.max(0, 999 - subtotal);
  return `<aside class="summary-card"><h2>Order summary</h2><div class="summary-line"><span>Subtotal</span><strong>${money(subtotal)}</strong></div><div class="summary-line"><span>Delivery</span><strong>${delivery ? money(delivery) : "FREE"}</strong></div>${more ? `<p class="summary-hint">Add ${money(more)} more for free delivery</p>` : ""}<div class="summary-line total"><span>Total</span><strong>${money(subtotal + delivery)}</strong></div>${includeButton ? `<a class="button" href="#/checkout" ${cart.length ? "" : 'aria-disabled="true"'}>Continue to checkout</a>` : ""}</aside>`;
}

function renderCart() {
  if (!cart.length) return `<div class="page-enter"><section class="section"><div class="wrap empty-state"><div class="empty-icon" aria-hidden="true">♧</div><h1>Your basket is taking a little break</h1><p>Pick out something creamy, crunchy and fresh from Panruti.</p><a class="button" href="#/shop">Browse cashews</a></div></section></div>`;
  const rows = cart.map(item => {
    const product = getProduct(item.productId);
    if (!product) return "";
    return `<article class="cart-row"><img src="assets/cashew-product.png" alt="${safe(product.name)}"><div><h3>${safe(product.name)}</h3><p>${safe(item.pack)} · ${money(priceFor(product, item.pack))} each</p></div><div class="qty-control" aria-label="Quantity for ${safe(product.name)}"><button type="button" data-qty="${safe(item.key)}" data-change="-1" aria-label="Decrease quantity">−</button><span>${item.quantity}</span><button type="button" data-qty="${safe(item.key)}" data-change="1" aria-label="Increase quantity">+</button></div><strong class="cart-price">${money(priceFor(product, item.pack) * item.quantity)}</strong><button type="button" class="text-button" data-remove="${safe(item.key)}">Remove</button></article>`;
  }).join("");
  return `<div class="page-enter"><section class="section"><div class="wrap"><div class="section-heading"><div><span class="eyebrow">Almost yours</span><h1>Your basket</h1></div><a class="text-button" href="#/shop">Keep shopping</a></div><div class="cart-layout"><div>${rows}</div>${renderSummary()}</div></div></section></div>`;
}

function stateOptions(selected = "") {
  return `<option value="">Select state</option>${STATES.map(state => `<option value="${safe(state)}" ${selected === state ? "selected" : ""}>${safe(state)}</option>`).join("")}`;
}

function field(name, label, type = "text", options = {}) {
  const required = options.required !== false;
  const value = options.value ?? "";
  const autocomplete = options.autocomplete ? ` autocomplete="${options.autocomplete}"` : "";
  const attrs = options.attrs || "";
  if (type === "select-state") return `<div class="form-field ${options.full ? "full" : ""}"><label for="${name}">${label}${required ? " *" : ""}</label><select class="field-control" id="${name}" name="${name}" ${required ? "required" : ""}${attrs}><option value="">Select state</option>${STATES.map(state => `<option value="${state}" ${value === state ? "selected" : ""}>${state}</option>`).join("")}</select><p class="field-error" aria-live="polite"></p></div>`;
  return `<div class="form-field ${options.full ? "full" : ""}"><label for="${name}">${label}${required ? " *" : ""}</label><input class="field-control" id="${name}" name="${name}" type="${type}" value="${safe(value)}" ${required ? "required" : ""}${autocomplete}${attrs}><p class="field-error" aria-live="polite"></p></div>`;
}

function renderCheckout() {
  return `<div class="page-enter"><section class="section"><div class="wrap"><div class="section-heading"><div><span class="eyebrow">One last step</span><h1>Checkout</h1></div></div>
    ${cart.length ? `<div class="checkout-layout"><form id="checkout-form" class="form-card" novalidate><h2>Delivery details</h2><div class="form-grid">
      ${field("name","Full name","text",{autocomplete:"name",attrs:'data-validate="name"'})}${field("mobile","Mobile number","tel",{autocomplete:"tel",attrs:'data-validate="mobile" inputmode="numeric" maxlength="10"'})}
      ${field("address","Address","text",{full:true,autocomplete:"street-address",attrs:'data-validate="address"'})}${field("city","City","text",{autocomplete:"address-level2",attrs:'data-validate="city"'})}${field("pincode","Pincode","text",{autocomplete:"postal-code",attrs:'data-validate="pincode" inputmode="numeric" maxlength="6"'})}
      ${field("state","State","select-state",{attrs:'data-validate="state"'})}
    </div><h2 style="margin-top:23px">Payment method</h2>
      <label class="radio-card"><input type="radio" name="payment" value="COD" checked><span><strong>Cash on delivery</strong><small>Pay when your fresh cashews arrive.</small></span></label>
      <label class="radio-card"><input type="radio" name="payment" value="UPI"><span><strong>UPI</strong><small>Pay with your preferred UPI app.</small></span></label>
      <div id="upi-field" class="form-field" hidden><label for="upiId">UPI ID *</label><input class="field-control" id="upiId" name="upiId" placeholder="name@bank" data-validate="upi"><p class="field-error" aria-live="polite"></p></div>
      <label class="radio-card"><input type="radio" name="payment" value="CARD"><span><strong>Debit / Credit card</strong><small>Secure payment handled by your bank. Card details are not collected here.</small></span></label>
      <p class="form-server-error" role="alert" hidden></p><button class="button form-submit" type="submit">Place order · ${money(cartSubtotal() + deliveryCost(cartSubtotal()))}</button>
    </form>${renderSummary(false)}</div>` : `<div class="empty-state"><h2>Your basket is empty</h2><a class="button" href="#/shop">Browse cashews</a></div>`}
  </div></section></div>`;
}

function authFormField(name, label, type, validate, autocomplete, extra = "") {
  return `<div class="form-field"><label for="${name}">${label} *</label><input class="field-control" id="${name}" name="${name}" type="${type}" required data-validate="${validate}" autocomplete="${autocomplete}" ${extra}><p class="field-error" aria-live="polite"></p></div>`;
}

function renderLogin() {
  return `<div class="page-enter"><section class="section"><div class="wrap auth-shell"><div class="section-heading"><span class="eyebrow">Welcome back</span><h1>Good to see you</h1><p>Your favourite Panruti cashews are just a sign-in away.</p></div>
  <form id="login-form" class="form-card" novalidate>${authFormField("identity","Email or mobile","text","identity","username")}<div class="form-field"><label for="password">Password *</label><input class="field-control" id="password" name="password" type="password" required data-validate="password" autocomplete="current-password"><p class="field-error" aria-live="polite"></p></div><p class="form-server-error" role="alert" hidden></p><label class="filter-option"><input type="checkbox" name="remember"> Remember me</label><button class="button form-submit" type="submit">Login</button><p class="auth-foot">New to Santhi Cashew? <a href="#/register">Create an account</a></p></form></div></section></div>`;
}

function renderRegister() {
  return `<div class="page-enter"><section class="section"><div class="wrap auth-shell"><div class="section-heading"><span class="eyebrow">Join our table</span><h1>Create your account</h1><p>A little more goodness, ready when you are.</p></div>
  <form id="register-form" class="form-card" novalidate><div class="form-grid">
    ${authFormField("name","Full name","text","name","name")}${authFormField("mobile","Mobile number","tel","mobile","tel",'inputmode="numeric" maxlength="10"')}
    ${authFormField("email","Email address","email","email","email")}${authFormField("password","Password","password","password","new-password")}
    ${authFormField("confirmPassword","Confirm password","password","confirm","new-password")}
    ${field("address","Address","text",{full:true,autocomplete:"street-address",attrs:'data-validate="address"'})}
    ${field("city","City","text",{autocomplete:"address-level2",attrs:'data-validate="city"'})}${field("pincode","Pincode","text",{autocomplete:"postal-code",attrs:'data-validate="pincode" inputmode="numeric" maxlength="6"'})}
    ${field("state","State","select-state",{attrs:'data-validate="state"'})}
  </div><div class="form-field" style="margin-top:12px"><label class="filter-option"><input id="terms" name="terms" type="checkbox" required data-validate="terms"> I agree to the terms and privacy policy *</label><p class="field-error" aria-live="polite"></p></div>
  <p class="form-server-error" role="alert" hidden></p><button class="button form-submit" type="submit">Create account</button><p class="auth-foot">Already have an account? <a href="#/login">Login</a></p></form></div></section></div>`;
}

function paymentLabel(payment) {
  return ({ COD: "Cash on delivery", UPI: "UPI", CARD: "Debit / Credit card", Card: "Debit / Credit card" })[payment] || payment || "Cash on delivery";
}

function orderStatus(order) {
  return String(order.status || order.orderStatus || "Placed").toLowerCase();
}

function renderOrders() {
  return `<div class="page-enter"><section class="section"><div class="wrap"><div class="section-heading"><div><span class="eyebrow">From our packing table to you</span><h1>My orders</h1></div></div><div id="orders-list" class="loading-state">Loading your orders…</div></div></section></div>`;
}

function orderCard(order) {
  const status = orderStatus(order);
  const cancelled = status.includes("cancel");
  const stages = ["placed", "packed", "shipped", "out for delivery", "delivered"];
  const statusIndex = stages.findIndex(stage => status.includes(stage));
  const items = order.items || order.products || [];
  const address = order.shipping || order.address || order.deliveryAddress || {};
  const addressText = typeof address === "string" ? address : [address.address, address.city, address.state, address.pincode].filter(Boolean).join(", ");
  const orderId = order.order_code || order.id || order._id || order.orderId || "—";
  const total = order.total ?? order.amount ?? order.totalAmount ?? 0;
  const createdAt = order.created_at || order.createdAt || order.date;
  const nextStage = stages[statusIndex + 1];
  const adminAction = userProfile?.is_admin && !cancelled && nextStage
    ? `<button class="button alt small" type="button" data-update-order="${safe(orderId)}" data-next-status="${safe(nextStage)}">Advance to ${safe(nextStage)}</button>`
    : "";
  return `<article class="order-card ${cancelled ? "cancelled" : ""}"><div class="order-head"><div><h3>Order ${safe(orderId)}</h3><span class="product-meta">${safe(new Date(createdAt || Date.now()).toLocaleDateString("en-IN",{ day:"numeric",month:"short",year:"numeric" }))} · ${safe(paymentLabel(order.payment_method || order.paymentMethod || order.payment))}</span></div><span class="status-pill ${cancelled ? "cancelled" : ""}">${safe(order.status || "Placed")}</span></div>
    ${!cancelled ? `<div class="stepper" aria-label="Order tracking">${stages.map((stage, index) => `<div class="step ${index <= statusIndex ? "done" : ""}"><i></i>${stage}</div>`).join("")}</div>` : ""}
    <div class="order-details"><div><strong>Items</strong><br>${items.length ? items.map(item => `${safe(item.name || item.productName || "Cashews")} · ${safe(item.size || "")} × ${safe(item.qty || item.quantity || 1)}`).join(", ") : "Cashews"}</div><div><strong>Delivery address</strong><br>${safe(addressText || "Address saved with order")}</div></div>
    <div class="order-head"><strong>Total ${money(total)}</strong><div class="order-actions">${adminAction}${!cancelled && statusIndex < 2 ? `<button class="button ghost small" type="button" data-cancel-order="${safe(orderId)}">Cancel order</button>` : ""}</div></div></article>`;
}

function renderSuccess() {
  const order = lastOrder || {};
  const id = order.order_code || order.orderCode || order.id || order._id || order.orderId || "placed successfully";
  const message = paymentLabel(order.payment_method || order.paymentMethod || order.payment || "COD") === "Cash on delivery" ? "You can pay when your fresh cashews arrive." : "Your payment will be confirmed by your payment provider.";
  return `<div class="page-enter"><section class="section"><div class="wrap success-panel"><div class="success-mark" aria-hidden="true">✓</div><span class="eyebrow">Freshness is on its way</span><h1>Thank you for your order!</h1><p>Your order number is <strong>${safe(id)}</strong>.</p><p>${safe(message)}</p><div class="success-actions"><a class="button" href="#/orders">View my orders</a><a class="button ghost" href="#/shop">Continue shopping</a></div></div></section></div>`;
}

function renderPage() {
  let { path, params } = routeInfo();
  if (["/orders", "/checkout"].includes(path) && !localStorage.getItem("sc_token")) {
    sessionStorage.setItem("sc_redirect_after_login", `#${location.hash.slice(1)}`);
    location.hash = "#/login";
    return;
  }
  if (path === "/shop") {
    shopFilters.category = params.get("category") || "";
  }
  if (path === "/success" && !lastOrder) {
    try {
      lastOrder = JSON.parse(sessionStorage.getItem("sc_last_order") || "null");
    } catch {
      lastOrder = null;
    }
  }
  const routes = { "/": renderHome, "/shop": renderShop, "/cart": renderCart, "/checkout": renderCheckout, "/success": renderSuccess, "/orders": renderOrders, "/login": renderLogin, "/register": renderRegister };
  const render = routes[path] || renderHome;
  document.getElementById("main").innerHTML = render();
  document.getElementById("main").focus({ preventScroll:true });
  document.querySelectorAll("#main form[novalidate]").forEach(bindFormValidation);
  updateCartCount();
  renderAuthLinks();
  setupReveals();
  if (path === "/shop") {
    bindShopPage();
    filterAndRenderShop();
  }
  if (path === "/orders") loadOrders();
  if (path === "/checkout") prefillCheckout();
  window.scrollTo(0, 0);
}

function setupReveals() {
  const items = document.querySelectorAll(".reveal");
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    items.forEach(item => item.classList.add("in"));
    return;
  }
  if (!("IntersectionObserver" in window)) {
    items.forEach(item => item.classList.add("in"));
    return;
  }
  if (revealObserver) revealObserver.disconnect();
  revealObserver = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add("in");
      revealObserver.unobserve(entry.target);
    }
  }), { threshold:.12 });
  items.forEach(item => revealObserver.observe(item));
}

function bindShopPage() {
  document.querySelectorAll("[data-category-chip]").forEach(button => button.addEventListener("click", () => {
    shopFilters.category = button.dataset.categoryChip;
    history.replaceState(null, "", `#/shop${shopFilters.category ? `?category=${encodeURIComponent(shopFilters.category)}` : ""}`);
    document.querySelectorAll("[data-category-chip]").forEach(chip => chip.classList.toggle("active", chip.dataset.categoryChip === shopFilters.category));
    filterAndRenderShop();
  }));
}

async function filterAndRenderShop() {
  const results = document.getElementById("shop-results");
  if (!results) return;
  const requestNumber = ++shopRequestNumber;
  if (!productApiAvailable) {
    const localResults = getShopProducts();
    const count = document.getElementById("shop-count");
    if (count) count.textContent = `${localResults.length} delicious ${localResults.length === 1 ? "choice" : "choices"}`;
    results.innerHTML = productGrid(localResults);
    return;
  }
  results.innerHTML = `<div class="loading-state">Finding your favourites…</div>`;
  const sortValues = { featured:"", low:"lo", high:"hi", name:"az" };
  const filters = {
    category:shopFilters.category,
    grade:shopFilters.grade,
    q:shopFilters.query,
    min_price:shopFilters.price === "mid" ? 250 : shopFilters.price === "over" ? 301 : undefined,
    max_price:shopFilters.price === "under" ? 249 : shopFilters.price === "mid" ? 300 : undefined,
    sort:sortValues[shopFilters.sort]
  };
  try {
    const filtered = await getProducts(filters);
    if (!results.isConnected || requestNumber !== shopRequestNumber) return;
    const mapped = filtered.map((product, index) => {
      const fallback = LOCAL_PRODUCTS.find(item => item.name === product.name) || LOCAL_PRODUCTS[index % LOCAL_PRODUCTS.length];
      const prices = Array.isArray(product.p)
        ? Object.fromEntries(product.p.map(pack => [pack.size, pack.price]))
        : product.prices || fallback.prices;
      return { ...fallback, ...product, id:productId(product), prices, reviews:product.review_count ?? product.reviews ?? fallback.reviews };
    });
    products = [...new Map([...products, ...mapped].map(product => [productId(product), product])).values()];
    const count = document.getElementById("shop-count");
    if (count) count.textContent = `${mapped.length} delicious ${mapped.length === 1 ? "choice" : "choices"}`;
    results.innerHTML = productGrid(mapped);
  } catch (error) {
    if (requestNumber !== shopRequestNumber) return;
    productApiAvailable = false;
    const localResults = getShopProducts();
    const count = document.getElementById("shop-count");
    if (count) count.textContent = `${localResults.length} delicious ${localResults.length === 1 ? "choice" : "choices"}`;
    results.innerHTML = productGrid(localResults);
    toast(`Showing the available cashew list. ${error.message}`, true);
  }
}

function addToCart(product, pack = "250 g", quantity = 1) {
  if (!product || stockOf(product) < 1) {
    toast("Sorry, this pack is out of stock.", true);
    return;
  }
  const key = `${productId(product)}::${pack}`;
  const current = cart.find(item => item.key === key);
  if (current && current.quantity + quantity > stockOf(product)) {
    toast("That is all the stock available for this cashew.", true);
    return;
  }
  if (current) current.quantity += quantity;
  else cart.push({ key, productId: productId(product), pack, quantity });
  persistCart();
  toast("Added to cart");
}

function migrateCartProductIds() {
  let changed = false;
  cart = cart.filter(item => {
    const localProduct = LOCAL_PRODUCTS.find(product => product.id === String(item.productId));
    if (localProduct) {
      const apiProduct = products.find(product => product.name === localProduct.name);
      if (apiProduct) {
        item.productId = productId(apiProduct);
        item.key = `${item.productId}::${item.pack}`;
        changed = true;
      }
    }
    const exists = Boolean(getProduct(item.productId));
    if (!exists) changed = true;
    return exists;
  });
  if (changed) persistCart();
}

function openProductModal(product) {
  if (!product) return;
  productModalReturn = document.activeElement;
  const modalRoot = document.getElementById("modal-root");
  const stock = stockOf(product);
  const prices = PACKS.map(pack => `<label class="pack-option"><input type="radio" name="pack" value="${pack}" ${pack === "250 g" ? "checked" : ""} ${stock === 0 ? "disabled" : ""}>${pack}<strong>${money(priceFor(product, pack))}</strong></label>`).join("");
  modalRoot.innerHTML = `<div class="modal-backdrop" data-modal-backdrop><section class="product-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" aria-describedby="modal-description">
    <button class="modal-close" type="button" data-close-modal aria-label="Close product details">×</button><div class="modal-product-grid">
    <div class="modal-image">${productImage(product)}</div><div class="modal-copy"><span class="eyebrow">${safe(formatCategory(product.category))} · ${safe(product.grade || "W320")}</span><h2 id="modal-title">${safe(product.name)}</h2>
    <div class="rating">★★★★★ <span>${safe(product.rating || 4.8)} · ${safe(product.reviews || 0)} reviews</span></div><p id="modal-description">${safe(product.description || "Carefully graded and freshly packed in Panruti, Tamil Nadu.")}</p>
    <strong>Choose your pack</strong><div class="pack-options">${prices}</div>
    <p class="product-meta">${stock === 0 ? "Out of stock" : stock < 10 ? `Only ${stock} left` : `${stock} in stock`} · FREE delivery above ₹999</p>
    <div class="modal-actions"><button class="button" type="button" data-modal-add ${stock === 0 ? "disabled" : ""}>Add to cart</button><button class="button alt" type="button" data-modal-buy ${stock === 0 ? "disabled" : ""}>Buy now</button></div></div></div>
    <table class="nutrition"><tbody><tr><th>Nutrition (per 100 g)</th><td>Typical values</td></tr><tr><th>Energy</th><td>553 kcal</td></tr><tr><th>Protein / Fat</th><td>18 g / 44 g</td></tr><tr><th>Carbs / Fibre</th><td>30 g / 3.3 g</td></tr><tr><th>Shelf life</th><td>6 months</td></tr><tr><th>Storage</th><td>Store in a cool, dry place</td></tr><tr><th>Ingredients</th><td>Cashew nuts</td></tr><tr><th>Best for</th><td>Snacking, cooking and gifting</td></tr><tr><th>Packaging</th><td>Vacuum-sealed pouch</td></tr><tr><th>Allergen</th><td>Contains tree nuts</td></tr><tr><th>Origin</th><td>Panruti, Tamil Nadu</td></tr></tbody></table>
    </section></div>`;
  modalRoot.querySelector("[data-close-modal]").focus();
}

function closeModal() {
  const root = document.getElementById("modal-root");
  if (!root.firstElementChild) return;
  root.innerHTML = "";
  if (productModalReturn && productModalReturn.isConnected) productModalReturn.focus();
}

function selectedModalPack() {
  return document.querySelector('#modal-root input[name="pack"]:checked')?.value || "250 g";
}

function formValue(form, name) {
  return String(new FormData(form).get(name) || "").trim();
}

function validationMessage(input) {
  const value = input.type === "checkbox" ? input.checked : input.value.trim();
  const rule = input.dataset.validate;
  if (input.required && !value) return "This field is required.";
  if (!value && !input.required) return "";
  if (rule === "name" && input.value.trim().length < 3) return "Please enter at least 3 characters.";
  if (rule === "mobile" && !/^[6-9]\d{9}$/.test(input.value.trim())) return "Enter a valid 10-digit Indian mobile number.";
  if (rule === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(input.value.trim())) return "Enter a valid email address.";
  if (rule === "identity" && !(/^[6-9]\d{9}$/.test(input.value.trim()) || /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(input.value.trim()))) return "Enter a valid email address or 10-digit mobile number.";
  if (rule === "password" && input.value.length < 8) return "Password must be at least 8 characters.";
  if (rule === "confirm" && input.value !== document.getElementById("register-form")?.elements.password.value) return "Passwords do not match.";
  if (rule === "address" && input.value.trim().length < 5) return "Address must be at least 5 characters.";
  if (rule === "city" && input.value.trim().length < 2) return "City must be at least 2 characters.";
  if (rule === "pincode" && !/^\d{6}$/.test(input.value.trim())) return "Enter a 6-digit pincode.";
  if (rule === "state" && !input.value) return "Please select a state.";
  if (rule === "upi" && !/^[\w.\-]{2,}@[a-zA-Z]{2,}$/.test(input.value.trim())) return "Enter a valid UPI ID, such as name@bank.";
  if (rule === "terms" && !input.checked) return "Please accept the terms to continue.";
  return "";
}

function validateField(input) {
  const container = input.closest(".form-field");
  const message = validationMessage(input);
  input.dataset.wasInvalid = String(Boolean(message));
  if (container) {
    container.classList.toggle("invalid", Boolean(message));
    const error = container.querySelector(".field-error");
    if (error) {
      error.textContent = message;
      if (message) error.setAttribute("role", "alert");
      else error.removeAttribute("role");
    }
  }
  return !message;
}

function validateForm(form) {
  const inputs = [...form.querySelectorAll("[data-validate]")].filter(input => input.type !== "hidden" && !input.closest("[hidden]"));
  const results = inputs.map(input => ({ input, valid:validateField(input) }));
  const firstInvalid = results.find(result => !result.valid);
  if (firstInvalid) firstInvalid.input.focus();
  return !firstInvalid;
}

function bindFormValidation(form) {
  form.querySelectorAll("[data-validate]").forEach(input => {
    input.addEventListener("blur", () => {
      input.dataset.touched = "true";
      validateField(input);
    });
    input.addEventListener("input", () => {
      if (input.dataset.touched === "true" || input.dataset.wasInvalid === "true") validateField(input);
    });
    input.addEventListener("change", () => {
      if (input.dataset.touched === "true" || input.dataset.wasInvalid === "true") validateField(input);
    });
  });
}

async function prefillCheckout() {
  const form = document.getElementById("checkout-form");
  if (!form || !localStorage.getItem("sc_token")) return;
  try {
    userProfile = await getProfile();
    renderAuthLinks();
    const profile = userProfile;
    ["name", "mobile", "address", "city", "pincode", "state"].forEach(key => {
      const input = form.elements.namedItem(key);
      const value = profile[key] ?? profile.phone ?? "";
      if (input && value) input.value = value;
    });
  } catch (error) {
    if (!localStorage.getItem("sc_token")) {
      sessionStorage.setItem("sc_redirect_after_login", "#/checkout");
      location.hash = "#/login";
      return;
    }
    toast(`Could not load your saved details: ${error.message}`, true);
  }
}

async function loadOrders() {
  const container = document.getElementById("orders-list");
  try {
    const orders = await getMyOrders();
    if (!container?.isConnected) return;
    container.className = "";
    container.innerHTML = orders.length ? orders.map(orderCard).join("") : `<div class="empty-state"><p>No orders yet. Let's find your first favourite.</p><a class="button" href="#/shop">Shop cashews</a></div>`;
  } catch (error) {
    if (!localStorage.getItem("sc_token")) {
      sessionStorage.setItem("sc_redirect_after_login", "#/orders");
      location.hash = "#/login";
      return;
    }
    if (container?.isConnected) container.innerHTML = `<div class="empty-state" role="alert"><p>We couldn't load your orders. ${safe(error.message)}</p><button class="button ghost" type="button" data-retry-orders>Try again</button></div>`;
    toast(`Couldn't load your orders: ${error.message}`, true);
  }
}

async function handleLogin(form) {
  clearServerError(form);
  if (!validateForm(form)) return;
  const identity = formValue(form, "identity");
  const payload = await login({ identity, password:formValue(form, "password") });
  userProfile = payload.user || getStoredUser();
  renderAuthLinks();
  toast("Welcome back!");
  const redirect = sessionStorage.getItem("sc_redirect_after_login");
  sessionStorage.removeItem("sc_redirect_after_login");
  location.hash = redirect || "#/";
}

async function handleRegister(form) {
  clearServerError(form);
  if (!validateForm(form)) return;
  const details = Object.fromEntries(new FormData(form).entries());
  delete details.confirmPassword;
  delete details.terms;
  const payload = await register(details);
  userProfile = payload.user || getStoredUser();
  renderAuthLinks();
  toast("Your account is ready. Welcome to Santhi Cashew!");
  const redirect = sessionStorage.getItem("sc_redirect_after_login");
  sessionStorage.removeItem("sc_redirect_after_login");
  location.hash = redirect || "#/";
}

async function handleCheckout(form) {
  if (!validateForm(form)) return;
  if (!cart.length) {
    toast("Your basket is empty.", true);
    return;
  }
  const data = Object.fromEntries(new FormData(form).entries());
  const orderData = {
    shipping: { name:data.name, mobile:data.mobile, address:data.address, city:data.city, pincode:data.pincode, state:data.state },
    items: cart.map(item => ({ product_id:Number(item.productId), size:item.pack, qty:item.quantity })),
    payment_method:data.payment,
    ...(data.payment === "UPI" ? { upi_id:data.upiId } : {})
  };
  const response = await placeOrder(orderData);
  lastOrder = response.order || response.data || response;
  lastOrder.payment_method = lastOrder.payment_method || data.payment;
  sessionStorage.setItem("sc_last_order", JSON.stringify(lastOrder));
  cart = [];
  persistCart();
  location.hash = "#/success";
}

async function handleNewsletter(form) {
  if (!form.reportValidity()) return;
  await subscribeNewsletter(form.elements.email.value.trim());
  form.reset();
  toast("You're on the list. Thanks for joining us!");
}

function handleDocumentClick(event) {
  const quickAdd = event.target.closest("[data-quick-add]");
  if (quickAdd) {
    event.stopPropagation();
    addToCart(getProduct(quickAdd.dataset.quickAdd));
    return;
  }
  const productCardElement = event.target.closest("[data-product]");
  if (productCardElement && event.target.closest("[data-open-product]")) {
    openProductModal(getProduct(productCardElement.dataset.product));
    return;
  }
  const addButton = event.target.closest("[data-modal-add]");
  if (addButton) {
    const product = getProduct(routeInfo().params.get("product")) || products.find(item => document.getElementById("modal-title")?.textContent === item.name);
    addToCart(product, selectedModalPack());
    return;
  }
  const buyButton = event.target.closest("[data-modal-buy]");
  if (buyButton) {
    const product = products.find(item => document.getElementById("modal-title")?.textContent === item.name);
    addToCart(product, selectedModalPack());
    closeModal();
    location.hash = "#/cart";
    return;
  }
  if (event.target.closest("[data-close-modal]") || event.target.matches("[data-modal-backdrop]")) {
    closeModal();
    return;
  }
  const qtyButton = event.target.closest("[data-qty]");
  if (qtyButton) {
    const item = cart.find(row => row.key === qtyButton.dataset.qty);
    const product = item && getProduct(item.productId);
    if (!item || !product) return;
    const next = item.quantity + Number(qtyButton.dataset.change);
    if (next <= 0) cart = cart.filter(row => row.key !== item.key);
    else if (next <= stockOf(product)) item.quantity = next;
    else { toast("That is all the stock available for this cashew.", true); return; }
    persistCart();
    renderPage();
    return;
  }
  const removeButton = event.target.closest("[data-remove]");
  if (removeButton) {
    cart = cart.filter(item => item.key !== removeButton.dataset.remove);
    persistCart();
    renderPage();
    toast("Removed from cart");
    return;
  }
  if (event.target.closest("[data-reset-filters]")) {
    shopFilters = { category:"", query:"", grade:"", price:"", sort:"featured" };
    renderPage();
    return;
  }
  if (event.target.closest("[data-retry-orders]")) loadOrders();
}

async function handleCancelOrder(button) {
  if (!window.confirm("Cancel this order?")) return;
  button.disabled = true;
  try {
    await cancelOrder(button.dataset.cancelOrder);
    toast("Your order has been cancelled.");
    await loadOrders();
  } catch (error) {
    button.disabled = false;
    toast(`Could not cancel this order: ${error.message}`, true);
  }
}

async function handleUpdateOrder(button) {
  button.disabled = true;
  try {
    await updateOrderStatus(button.dataset.updateOrder, button.dataset.nextStatus);
    toast(`Order moved to ${button.dataset.nextStatus}.`);
    await loadOrders();
  } catch (error) {
    button.disabled = false;
    toast(`Could not update order status: ${error.message}`, true);
  }
}

function logout() {
  clearAuth();
  userProfile = null;
  renderAuthLinks();
  sessionStorage.removeItem("sc_redirect_after_login");
  toast("You have been logged out.");
  location.hash = "#/";
}

function initTheme() {
  const saved = localStorage.getItem("sc_theme");
  if (saved === "dark" || saved === "light") document.documentElement.dataset.theme = saved;
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const current = document.documentElement.dataset.theme || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("sc_theme", next);
  });
}

function bindGlobalEvents() {
  document.addEventListener("click", event => {
    handleDocumentClick(event);
    if (event.target.closest("#logout-button")) {
      logout();
      return;
    }
    const cancel = event.target.closest("[data-cancel-order]");
    if (cancel) handleCancelOrder(cancel);
    const update = event.target.closest("[data-update-order]");
    if (update) handleUpdateOrder(update);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeModal();
    if (event.key === "Tab" && document.querySelector('[role="dialog"]')) {
      const dialog = document.querySelector('[role="dialog"]');
      const focusable = [...dialog.querySelectorAll('button:not(:disabled),input:not(:disabled),a[href]')];
      if (!focusable.length) return;
      if (event.shiftKey && document.activeElement === focusable[0]) {
        event.preventDefault();
        focusable.at(-1).focus();
      } else if (!event.shiftKey && document.activeElement === focusable.at(-1)) {
        event.preventDefault();
        focusable[0].focus();
      }
    }
  });
  document.addEventListener("input", event => {
    if (event.target.id === "shop-search") {
      shopFilters.query = event.target.value;
      window.clearTimeout(window.shopSearchTimer);
      window.shopSearchTimer = window.setTimeout(filterAndRenderShop, 250);
    }
  });
  document.addEventListener("change", event => {
    if (event.target.matches('input[name="grade"]')) {
      shopFilters.grade = event.target.value;
      filterAndRenderShop();
    } else if (event.target.matches('input[name="price"]')) {
      shopFilters.price = event.target.value;
      filterAndRenderShop();
    } else if (event.target.id === "sort-products") {
      shopFilters.sort = ({ low:"low", high:"high", name:"name" })[event.target.value] || "featured";
      filterAndRenderShop();
    }
  });
  document.addEventListener("submit", async event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.id === "header-search") {
      event.preventDefault();
      shopFilters.query = document.getElementById("header-query").value;
      shopFilters.category = document.getElementById("header-category").value;
      location.hash = `#/shop${shopFilters.category ? `?category=${encodeURIComponent(shopFilters.category)}` : ""}`;
    } else if (["login-form", "register-form", "checkout-form"].includes(form.id)) {
      event.preventDefault();
      clearServerError(form);
      const submitButton = form.querySelector('[type="submit"]');
      const originalLabel = submitButton?.textContent;
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = form.id === "checkout-form" ? "Placing your order…" : "Please wait…";
      }
      try {
        if (form.id === "login-form") await handleLogin(form);
        if (form.id === "register-form") await handleRegister(form);
        if (form.id === "checkout-form") await handleCheckout(form);
      } catch (error) {
        showServerError(form, error);
      } finally {
        if (submitButton?.isConnected) {
          submitButton.disabled = false;
          submitButton.textContent = originalLabel;
        }
      }
    } else if (form.id === "newsletter-form") {
      event.preventDefault();
      const submitButton = form.querySelector('[type="submit"]');
      const originalLabel = submitButton?.textContent;
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Subscribing…";
      }
      try { await handleNewsletter(form); }
      catch (error) { toast(`Couldn't subscribe: ${error.message}`, true); }
      finally {
        if (submitButton?.isConnected) {
          submitButton.disabled = false;
          submitButton.textContent = originalLabel;
        }
      }
    }
  });
  document.addEventListener("focusout", event => {
    if (event.target.matches("#register-form [name=password]")) {
      const confirm = document.getElementById("confirmPassword");
      if (confirm?.value) validateField(confirm);
    }
  });
  document.addEventListener("change", event => {
    if (event.target.name === "payment") {
      const upiField = document.getElementById("upi-field");
      if (!upiField) return;
      const show = event.target.value === "UPI";
      upiField.hidden = !show;
      document.getElementById("upiId").required = show;
    }
  });
  document.getElementById("menu-toggle").addEventListener("click", event => {
    const nav = document.querySelector(".main-nav");
    const open = nav.classList.toggle("open");
    event.currentTarget.setAttribute("aria-expanded", String(open));
    event.currentTarget.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  });
  document.addEventListener("pointermove", event => {
    const hero = document.getElementById("hero-parallax");
    if (!hero) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      hero.style.transform = "";
      return;
    }
    const bounds = hero.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) {
      hero.style.transform = "";
      return;
    }
    const x = (event.clientX - bounds.left) / bounds.width - .5;
    const y = (event.clientY - bounds.top) / bounds.height - .5;
    hero.style.transform = `rotateY(${x * 10}deg) rotateX(${-y * 10}deg)`;
  });
  document.addEventListener("pointermove", event => {
    const card = event.target.closest(".tilt-card");
    if (!card || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = card.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - .5;
    const y = (event.clientY - rect.top) / rect.height - .5;
    card.style.transform = `perspective(850px) rotateY(${x * 5}deg) rotateX(${-y * 5}deg) translateY(-2px)`;
  });
  document.addEventListener("pointerout", event => {
    const hero = event.target.closest("#hero-parallax");
    if (hero && !hero.contains(event.relatedTarget)) hero.style.transform = "";
    const card = event.target.closest(".tilt-card");
    if (card && !card.contains(event.relatedTarget)) card.style.transform = "";
  });
  window.addEventListener("hashchange", () => {
    document.querySelector(".main-nav").classList.remove("open");
    document.getElementById("menu-toggle").setAttribute("aria-expanded", "false");
    document.getElementById("menu-toggle").setAttribute("aria-label", "Open menu");
    renderPage();
  });
  window.addEventListener("sc-auth-changed", () => {
    userProfile = null;
    renderAuthLinks();
  });
}

async function init() {
  document.getElementById("year").textContent = new Date().getFullYear();
  initTheme();
  bindGlobalEvents();
  if (localStorage.getItem("sc_token")) userProfile = getStoredUser();
  renderAuthLinks();
  try {
    const apiProducts = await getProducts();
    products = apiProducts.map((product, index) => {
      const fallback = LOCAL_PRODUCTS.find(item => item.id === String(product.id) || item.name === product.name) || LOCAL_PRODUCTS[index % LOCAL_PRODUCTS.length];
      const priceData = Array.isArray(product.p)
        ? Object.fromEntries(product.p.map(pack => [pack.size, pack.price]))
        : product.prices || product.pricing || (product.price ? { "250 g":product.price } : fallback.prices);
      return {
        ...fallback,
        ...product,
        id:productId(product),
        category:formatCategory(product.category || fallback.category),
        grade:product.grade || fallback.grade,
        prices:priceData,
        reviews:product.review_count ?? product.reviews ?? fallback.reviews
      };
    });
    migrateCartProductIds();
  } catch (error) {
    productApiAvailable = false;
    products = LOCAL_PRODUCTS.map(product => ({ ...product }));
    toast(`Showing our local catalogue. ${error.message}`, true);
  }
  if (localStorage.getItem("sc_token")) {
    try {
      userProfile = await getProfile();
    } catch (error) {
      if (localStorage.getItem("sc_token")) toast(`Couldn't refresh your profile: ${error.message}`, true);
    }
  }
  renderAuthLinks();
  renderPage();
}

init();
