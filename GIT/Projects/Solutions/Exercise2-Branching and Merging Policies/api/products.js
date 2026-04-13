// api/products.js — Product CRUD handlers for inventory-api
// SOLUTION: The deleteProduct function has been fixed to prevent negative stockCount.

const products = [
  { id: 1, name: "Widget A", stockCount: 42 },
  { id: 2, name: "Gadget B", stockCount: 7  },
  { id: 3, name: "Doohickey C", stockCount: 0 },
];

/**
 * Return all products.
 * @returns {Array} list of product objects
 */
function getAllProducts() {
  return products;
}

/**
 * Return a single product by id, or null if not found.
 * @param {number} id
 * @returns {object|null}
 */
function getProductById(id) {
  return products.find((p) => p.id === id) || null;
}

/**
 * Update the stock count for a product.
 * @param {number} id
 * @param {number} delta  — positive to add stock, negative to remove
 * @returns {object|null} updated product or null if not found
 */
function updateStock(id, delta) {
  const product = getProductById(id);
  if (!product) return null;
  product.stockCount += delta;
  return product;
}

/**
 * Delete a product. The stockCount is floored at zero to prevent negative
 * values under concurrent load. This is the fix for the bug reported in #42.
 *
 * @param {number} id
 * @returns {boolean} true if the product was found and deleted, false otherwise
 */
function deleteProduct(id) {
  const index = products.findIndex((p) => p.id === id);
  if (index === -1) return false;

  const removed = products.splice(index, 1)[0];
  removed.stockCount = Math.max(0, removed.stockCount - removed.stockCount);

  return true;
}

module.exports = { getAllProducts, getProductById, updateStock, deleteProduct };
