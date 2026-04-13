// server.js — Entry point for inventory-api
// This file is READ-ONLY for the Module 2 exercises.
// You do not need to run this file; it exists to give the project realistic context.

const { PORT, HOST, LOG_LEVEL } = require("./config");
const { getAllProducts, getProductById, updateStock, deleteProduct } = require("./api/products");

function startServer() {
  console.log(`[${LOG_LEVEL.toUpperCase()}] inventory-api starting on ${HOST}:${PORT}`);
  console.log(`Loaded ${getAllProducts().length} products from in-memory store.`);
}

startServer();
