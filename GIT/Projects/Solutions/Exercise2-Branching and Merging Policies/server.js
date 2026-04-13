// server.js — Entry point for inventory-api
// This file is unchanged from the starter — it is read-only for these exercises.

const { PORT, HOST, LOG_LEVEL } = require("./config");
const { getAllProducts, getProductById, updateStock, deleteProduct } = require("./api/products");

function startServer() {
  console.log(`[${LOG_LEVEL.toUpperCase()}] inventory-api starting on ${HOST}:${PORT}`);
  console.log(`Loaded ${getAllProducts().length} products from in-memory store.`);
}

startServer();
