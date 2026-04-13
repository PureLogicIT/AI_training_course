// config.js — Application configuration for inventory-api
// SOLUTION: Final state of config.js on the develop branch after both
// feature/request-logging (--no-ff merge) and feature/rate-limiting
// (squash merge + conflict resolution) have landed.

const PORT = 3000;
const HOST = "0.0.0.0";
const LOG_LEVEL = "debug";
const DB_POOL_SIZE = 5;
const DB_TIMEOUT_MS = 2000;

// Request logging settings  (from feature/request-logging, merged with --no-ff)
const REQUEST_LOG_ENABLED = true;
const REQUEST_LOG_FORMAT = "combined";

// Rate limiting settings  (from feature/rate-limiting, landed via squash merge)
const RATE_LIMIT_WINDOW_MS = 60000;
const RATE_LIMIT_MAX_REQUESTS = 100;
const RATE_LIMIT_MESSAGE = "Too many requests, please try again later.";

module.exports = {
  PORT,
  HOST,
  LOG_LEVEL,
  DB_POOL_SIZE,
  DB_TIMEOUT_MS,
  REQUEST_LOG_ENABLED,
  REQUEST_LOG_FORMAT,
  RATE_LIMIT_WINDOW_MS,
  RATE_LIMIT_MAX_REQUESTS,
  RATE_LIMIT_MESSAGE,
};
