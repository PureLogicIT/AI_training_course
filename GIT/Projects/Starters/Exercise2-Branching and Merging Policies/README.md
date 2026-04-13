# inventory-api

A minimal inventory management back-end. This starter project is used for
GIT Module 2 exercises on branching strategies, merge conflict resolution,
and git stash.

## Project Structure

```
inventory-api/
├── api/
│   └── products.js     # Product CRUD handlers (contains a known bug — see exercises)
├── alerts.js           # Low-stock alert system (stub — to be completed)
├── config.js           # Application configuration constants
├── server.js           # Entry point (read-only for these exercises)
└── README.md
```

## Exercise Instructions

See `GIT/Exercises/Exercise2-Branching and Merging Policies.md` for the
full step-by-step instructions.

**Do not initialize a Git repository yet** — the exercises walk you through
`git init` as the first step.

## Notes

- No Node.js installation is required. The `.js` files are plain JavaScript
  that you will edit as text during the exercises.
- The bug in `api/products.js` is intentional. Look for the `// BUGFIX NEEDED`
  comment in the `deleteProduct` function.
