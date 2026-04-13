// alerts.js — Low-stock alert system for inventory-api
// SOLUTION: sendLowStockAlert implemented after recovering from git stash.

const LOW_STOCK_THRESHOLD = 10;

function sendLowStockAlert(productId, currentQty) {
  console.log(`[ALERT] Product ${productId} has low stock: ${currentQty} units remaining.`);
}

module.exports = { LOW_STOCK_THRESHOLD, sendLowStockAlert };
