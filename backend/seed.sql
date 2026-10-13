USE santhi_cashew;

INSERT INTO products
  (name, category, grade, description, ingredients, best_for,
   price_250, price_500, price_1kg, stock, rating, review_count, image_url)
VALUES
  ('Whole Cashew W320', 'Raw', 'W320',
   'Classic creamy whole kernels, ideal for everyday snacking and cooking.',
   'Cashew nuts', 'Everyday snacking and cooking', 229.00, 550.00, 900.00, 120, 4.8, 128, 'assets/cashew-product.png'),
  ('Premium Jumbo W180', 'Raw', 'W180',
   'Our largest, plumpest kernels. Sweet, buttery and beautifully uniform.',
   'Cashew nuts', 'Premium snacking and gifting', 299.00, 400.00, 750.00, 40, 4.9, 84, 'assets/cashew-product.png'),
  ('Roasted Salted', 'Roasted', 'W240',
   'Slow roasted in small batches with a light dusting of sea salt.',
   'Cashew nuts, sea salt', 'Savoury snacking', 269.00, 600.00, 950.00, 8, 4.7, 96, 'assets/w240-cashews.png'),
  ('Pepper Masala', 'Flavoured', 'W320',
   'Roasted cashews tossed in Kerala black pepper and house masala.',
   'Cashew nuts, black pepper, spices', 'A spicy teatime snack', 279.00, 550.00, 900.00, 60, 4.8, 51, 'assets/cashew-product.png'),
  ('Cashew Pieces', 'Raw', 'Broken',
   'Broken kernels at a friendly price, perfect for sweets, gravies and baking.',
   'Cashew nuts', 'Sweets, gravies and baking', 179.00, 340.00, 660.00, 200, 4.6, 73, 'assets/cashew-product.png'),
  ('Festive Gift Box', 'Gift', 'W240',
   'Roasted and raw cashews in a keepsake box for Diwali, Pongal and weddings.',
   'Cashew nuts', 'Festive gifting and celebrations', 399.00, 600.00, 950.00, 0, 4.9, 32, 'assets/w240-cashews.png')
ON DUPLICATE KEY UPDATE
  category = VALUES(category),
  grade = VALUES(grade),
  description = VALUES(description),
  ingredients = VALUES(ingredients),
  best_for = VALUES(best_for),
  price_250 = VALUES(price_250),
  price_500 = VALUES(price_500),
  price_1kg = VALUES(price_1kg),
  stock = VALUES(stock),
  rating = VALUES(rating),
  review_count = VALUES(review_count),
  image_url = VALUES(image_url),
  is_active = TRUE;
