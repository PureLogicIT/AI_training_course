# Solution Notes — Exercise 2: Branching and Merging Policies

This file explains the key decisions made during each part of the exercise.
Use it to check your understanding after completing the exercises on your own.

---

## Exercise 1: Git Flow Hotfix With a Stash Escape Hatch

### Why annotated tags instead of lightweight tags?

Annotated tags (`git tag -a`) store a tagger name, email, date, and message as
a full Git object. Lightweight tags are just a pointer (like a branch that never
moves). For release tagging you should always use annotated tags so that
`git describe`, `git log --decorate`, and release tooling can distinguish a
release tag from a temporary bookmark.

### Why `-u` on the stash push?

`alerts.js` was modified but had never been staged. Without the `-u` flag,
`git stash push` only stashes changes to already-tracked files. The `-u`
(untracked) flag ensures untracked-but-modified files are included. If you
omit it, `alerts.js` will still be in your working directory when you switch
branches, and on some systems Git will carry it over to the hotfix branch,
contaminating the fix.

### Why create the hotfix branch from main, not develop?

In Git Flow, `hotfix/*` branches always start from `main` because `main`
represents the production state. `develop` may contain unreleased,
incomplete work. Starting the hotfix from `develop` would risk shipping
unfinished features to production when you merge back to `main`.

### Why --no-ff for both merges?

`--no-ff` (no fast-forward) forces a merge commit even when a fast-forward
would be possible. The resulting merge commit node in the graph permanently
records that a set of commits was developed as a named unit (`hotfix/negative-stock-count`).
This is invaluable when tracing a regression: you can see exactly which merge
introduced the hotfix, rather than having individual commits floating on `main`
with no clear grouping.

### Why merge into develop as well?

If you only merge the hotfix into `main`, the next time `develop` is merged
into `main` (e.g., for the next release), the hotfix change will appear to
be "removed" because `develop` still has the original, unfixed code.
Merging into both branches keeps the histories synchronized and prevents
regressions at the next release.

---

## Exercise 2: Squash Merges and Three-Way Conflict Resolution

### Why --no-ff for feature/request-logging but --squash for feature/rate-limiting?

`feature/request-logging` had one clean, well-named commit. A `--no-ff` merge
preserves that single commit in history with a merge commit node that shows it
arrived as a named feature. The overhead is one extra commit, and the benefit
is clear authorship and traceability.

`feature/rate-limiting` had three commits: two "wip" commits and one final
commit. Landing all three on `develop` would pollute `git log` and make
`git bisect` harder to use. The squash merge collapses all three into a
single, well-described commit. The trade-off is that the individual commit
authors are no longer visible on `develop` — a concern for large teams, but
acceptable here.

### Why not rebase instead of squash?

Rebase (`git rebase develop` on the feature branch, then `git merge --ff-only`)
would also produce a linear history. However, rebase rewrites commit hashes.
If the feature branch had been pushed and another developer had branched from
it, rebasing would break their history. Squash merge avoids that risk because
it creates a brand-new commit on `develop` rather than rewriting the source
branch.

### Why keep both sides of the conflict?

The conflict in `config.js` arose because both branches appended new constants
to the end of the same file. Neither side's changes are wrong — they are
independent, additive features. Using `git checkout --ours` would discard the
rate-limiting constants; using `git checkout --theirs` would discard the
request-logging constants. The correct resolution is to keep both blocks,
which is why manual editing was required.

### Why git restore --staged instead of git reset HEAD?

`git restore --staged <file>` is the modern command (Git 2.23+) for unstaging
a file without touching the working directory. It does exactly one thing,
with no ambiguity. `git reset HEAD <file>` has the same effect in most
contexts but `git reset` also has destructive forms (`--hard`, `--mixed`,
`--soft`) that can accidentally discard work if mistyped. Prefer `git restore
--staged` in interactive use to reduce the risk of destructive mistakes.

### Why git branch -D (uppercase) after the squash merge?

A squash merge copies the changes from the source branch into a new commit on
the target, but it does NOT move the source branch pointer into the target's
ancestry. From Git's perspective, `feature/rate-limiting` is still "not merged"
into `develop` — the commits in that branch are simply not reachable from
`develop`'s ancestry graph. `git branch -d` (lowercase) checks reachability and
refuses to delete an "unmerged" branch as a safety net. Since you know the
changes were intentionally squash-merged, `git branch -D` (uppercase) overrides
that safety check and forces the deletion.

---

## Recommended git log Aliases

Add these to your global git config to make graph visualization easier:

```bash
git config --global alias.lg "log --oneline --graph --all --decorate"
git config --global alias.lg1 "log --oneline --graph --decorate"
```

Usage:
```bash
git lg      # full topology of all branches
git lg1     # topology of current branch only
```
