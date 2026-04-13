// config.js — Application configuration for inventory-api
// This file is modified by multiple branches in Exercise 2.

const PORT = 3000;
const HOST = "0.0.0.0";
const LOG_LEVEL = "info";
const DB_POOL_SIZE = 5;
const DB_TIMEOUT_MS = 2000;

module.exports = { PORT, HOST, LOG_LEVEL, DB_POOL_SIZE, DB_TIMEOUT_MS };
