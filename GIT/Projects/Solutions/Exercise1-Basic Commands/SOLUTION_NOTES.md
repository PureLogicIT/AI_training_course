# Solution Notes — Exercise 1: Basic Commands

This document explains the key decisions made in the reference solution, what the
expected Git history looks like after completing all three exercises, and how each
file maps to the exercise steps.

---

## Exercise 1 of 3: The Staging Area Is Not Your Working Directory

### Key decisions

**Why `.gitignore` is committed first (before the other files).**
The module's Best Practice 6 says to create `.gitignore` before the first commit.
The solution follows a two-commit initial setup:

1. `Add .gitignore: exclude .env, __pycache__, venv` — only `.gitignore` is staged.
2. `Initial commit: add devlog skeleton and README` — source files are staged second.

This ordering guarantees `.env` can never accidentally slip into the initial commit,
even if someone runs `git add .` instead of naming files individually.

**Why `config.py` ends up with two separate commits.**
The exercise in Part C requires learners to use `git add -p` to split a single
editing session into two focused commits:

- Commit 3: `Update default log file path in config` — only the `LOG_FILE` value change.
- Commit 4: `Add MAX_ENTRIES limit constant to config` — only the new constant.

In the solution's `config.py`, `LOG_FILE` is `"devlog_entries.txt"` (changed from the
starter's `"devlog.txt"`) and `MAX_ENTRIES = 100` is present. Both changes are in the
file, but the commit history records them separately.

**The `log_entry` function implementation.**
The starter intentionally leaves `log_entry` as a stub returning `None`. The solution
implements it with file I/O and a sequential ID derived by counting existing lines.
This is intentionally simple — the function does not need to be production-quality.
Learners may implement it differently; what matters is that it returns a dict and the
function body is not just `pass`.

---

## Exercise 2 of 3: Branch, Diverge, Conflict, Resolve

### Key decisions

**Why `feature/search` and `feature/delete` both modify `run()` on overlapping lines.**
A merge conflict only occurs when two branches modify the *same lines* of the same
file. The exercise requires learners to engineer this deliberately by having both
branches add TODOs or calls inside the `run()` function body. The solution's
`devlog.py` shows the *resolved* state — `run()` dispatches to both `search_entries`
and `delete_entry` — which is what a correctly resolved conflict looks like.

**Why `--no-ff` is used for both merges.**
The first merge (fast-forward eligible) uses `--no-ff` because the exercise explicitly
instructs it and the module's Best Practice 8 recommends it for feature branches. This
creates a merge commit that preserves the context that these commits were developed
together as a named feature.

The second merge (conflict merge) creates a merge commit automatically because the
histories have genuinely diverged.

**Expected commit graph shape after Exercise 2.**

```
*   Merge feature/delete: resolve run() conflict, integrate delete capability
|\
| * Add delete_entry stub and wire into run()
* |   Merge feature/search: add keyword search capability
|\ \
| * | Add search_entries stub and wire into run()
|/ /
* / Add MAX_ENTRIES limit constant to config
* Update default log file path in config
* Initial commit: add devlog skeleton and README
* Add .gitignore: exclude .env, __pycache__, venv
```

The exact hashes will differ, but this topology is what `git log --oneline --graph --all --decorate` should produce on a completed Exercise 2 repository.

---

## Exercise 3 of 3: Simulating a Remote Workflow Without GitHub

### Key decisions

**Why a bare repository instead of a real remote.**
Using `git init --bare` to create a local bare repository lets learners practice every
remote workflow command (`git remote add`, `git push -u`, `git clone`, `git pull`,
`git fetch`) without any network dependency, account setup, or authentication. The
behavior is identical to a real remote: pushes are rejected when out of date, pull
creates a fetch + integrate cycle, and clone sets up `origin` automatically.

**Why the diverged-history scenario is engineered in Part D.**
The `--rebase` pull strategy only has a visible effect when both the local branch and
the remote branch have new commits since their last common ancestor. Part D engineers
this by:
1. Having machine B commit and push `CHANGELOG.md`.
2. Having machine A commit a README change *without pulling first*.
3. Attempting `git push` on machine A, which is rejected.

This rejection is the learning moment — it mirrors the real-world situation described
in the module's Pitfall 4 and Best Practice 7.

**Why `git pull --rebase` produces a linear history.**
After rebase, the local commit (`README.md` update) is replayed on top of the remote
commit (`CHANGELOG.md` addition), producing a straight-line graph:

```
* Add Usage section to README          ← machine A's commit, rebased
* Add initial CHANGELOG                ← machine B's commit
* <previous history from Exercise 2>
```

Compare this to what `git pull` (merge strategy) would produce:

```
*   Merge branch 'main' of .../devlog.git   ← unnecessary noise
|\
| * Add initial CHANGELOG
* | Add Usage section to README
|/
* <previous history>
```

The rebase result is cleaner and easier to read in `git log --oneline`.

**`CHANGELOG.md` is included in the solution.**
This file is created during Exercise 3 Part C on "machine B". It is included in the
solution directory so the solution files represent the final state of the repository
after all three exercises are complete.

---

## File Mapping to Exercise Steps

| File | Created / modified in | Exercise step |
|---|---|---|
| `.gitignore` | Created | Ex 1, Part A, step 4–6 |
| `README.md` | Created initially | Ex 1, Part A, step 7 |
| `README.md` | Updated (Usage section) | Ex 3, Part D, step 13 |
| `devlog.py` | Created initially | Ex 1, Part A, step 7 |
| `devlog.py` | `log_entry` implemented | Ex 1, Part B, steps 9–13 |
| `devlog.py` | `search_entries` added | Ex 2, Part A, steps 3–4 |
| `devlog.py` | `delete_entry` added + conflict resolved | Ex 2, Part C, steps 15–19 |
| `config.py` | `LOG_FILE` path changed | Ex 1, Part C, step 17 |
| `config.py` | `MAX_ENTRIES` added | Ex 1, Part C, step 18 |
| `CHANGELOG.md` | Created | Ex 3, Part C, step 10 |
| `.env` | Present but never committed | Ex 1, Part A (verified never staged) |

---

## Verification Commands

Run these from the completed Exercise 3 directory to confirm all outcomes:

```bash
# Exercise 1 outcomes
git log --oneline | wc -l          # Should be >= 8 (4 base + 2 merge + 2 feature)
git status                          # nothing to commit, working tree clean
git log --all --full-history -- .env  # No output (never committed)

# Exercise 2 outcomes
git log --oneline --graph --all     # Two merge nodes visible
git branch                          # Only 'main' listed

# Exercise 3 outcomes
git remote -v                       # origin points to bare repo or GitHub
git branch -a                       # remotes/origin/main visible
git log --oneline --graph           # Linear history, no merge commit between CHANGELOG and README commits
```
