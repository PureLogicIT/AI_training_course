# inventory-api

A minimal inventory management back-end. This is the **solution** project for
GIT Module 2 exercises on branching strategies, merge conflict resolution,
and git stash.

## Project Structure

```
inventory-api/
├── api/
│   └── products.js     # Bug fixed: Math.max(0, ...) guards deleteProduct
├── alerts.js           # sendLowStockAlert implemented (recovered from stash)
├── config.js           # All six config constants present after conflict resolution
├── server.js           # Entry point (unchanged)
├── README.md
└── SOLUTION_NOTES.md   # Explains key decisions made during the exercises
```

## Expected Git History Shape

After completing both exercises, `git log --oneline --graph --all --decorate`
should produce a graph similar to this (hashes will differ):

```
* abc1234 (feature/low-stock-alerts) feat: add sendLowStockAlert function
* def5678 feat: add rate limiting configuration (window, max requests, error message)
*   ghi9012 Merge feature/request-logging into develop
|\
| * jkl3456 feat: add request logging configuration
* | mno7890 Merge hotfix/negative-stock-count into develop
|\|
| *   pqr2345 (tag: v1.0.1, main) Merge hotfix/negative-stock-count into main
| |\
| | * stu6789 fix: prevent negative stock count on concurrent delete+update (#42)
| |/
* | vwx0123 config: enable debug logging on develop for integration testing
|/
* yza4567 (tag: v1.0.0) Initial commit: inventory-api v1.0.0 baseline
```

Key observations:
- `main` and `develop` are both permanent branches
- Two annotated tags (`v1.0.0`, `v1.0.1`) mark production releases
- The hotfix merge commit appears on BOTH `main` and `develop` (two separate `--no-ff` merges)
- The `feature/request-logging` merge shows as a fork-and-join node (due to `--no-ff`)
- The rate-limiting feature appears as a single straight commit (squash merge — no fork node)
- `feature/low-stock-alerts` is still open (not yet merged into `develop`)
