// api/products.js — Product CRUD handlers for inventory-api
//
// *** THIS FILE CONTAINS AN INTENTIONAL BUG in deleteProduct ***
// The bug causes stockCount to go negative when a delete and an update
// arrive concurrently. Find the BUGFIX NEEDED comment and fix it.

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
 * Delete a product and decrement the stockCount by the product's current value.
 *
 * BUGFIX NEEDED: The current implementation can produce a negative stockCount
 * when a concurrent update races with a deletion. The fix is a one-liner:
 * wrap the subtraction result in Math.max(0, ...) so the count never goes
 * below zero.
 *
 * @param {number} id
 * @returns {boolean} true if the product was found and deleted, false otherwise
 */
function deleteProduct(id) {
  const index = products.findIndex((p) => p.id === id);
  if (index === -1) return false;

  // BUG: this can go negative under concurrent load
  const removed = products.splice(index, 1)[0];
  removed.stockCount = removed.stockCount - removed.stockCount; // always 0, but wrong pattern

  return true;
}

module.exports = { getAllProducts, getProductById, updateStock, deleteProduct };
