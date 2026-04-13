# Module 3: Advanced Topics
> Subject: GIT | Difficulty: Advanced | Estimated Time: 270 minutes

## Objective

After completing this module, you will be able to rewrite and clean up commit history using interactive rebase, apply targeted commits across branches with `git cherry-pick`, locate the exact commit that introduced a bug using `git bisect`, recover lost work from the reflog, choose confidently between `git reset`, `git revert`, and `git restore` for different undo scenarios, manage versioned releases with annotated tags and semantic versioning, embed external repositories as submodules, work on multiple branches simultaneously using `git worktree`, automate code quality checks with Git hooks, and extract meaningful insight from the repository history using advanced log and blame techniques.

## Prerequisites

- Completion of **Module 1: Basic Commands** — you must be comfortable with `git init`, `git add`, `git commit`, `git log`, `git diff`, `git branch`, `git checkout`, `git push`, and `git pull`
- Completion of **Module 2: Branching and Merging Policies** — you must understand fast-forward vs. three-way merges, rebase concepts, `git stash`, `git switch`, and `git restore`
- Git 2.40 or later installed (`git --version`; current stable release is 2.53.0)
- Comfort editing files in a terminal-based editor (nano, vim, or any editor opened by `git` via `$EDITOR`)
- A basic understanding of shell scripting is helpful for the Hooks section but is not required

## Key Concepts

---

### Interactive Rebase — Rewriting History with Precision

`git rebase -i` (interactive rebase) is the most powerful history-editing tool in Git. It lets you modify any sequence of commits before they are pushed: combining messy work-in-progress commits into clean logical units, fixing typos in messages, reordering commits for narrative clarity, splitting an oversized commit, or removing experimental work that should never have been committed.

The fundamental command opens an editor listing the last N commits, oldest first:

```bash
git rebase -i HEAD~N
```

Each line in the editor represents one commit. You change the verb at the start of the line to control what Git does with that commit.

**Available commands (shown verbatim in the rebase editor):**

| Verb | Short | Effect |
|------|-------|--------|
| `pick` | `p` | Use the commit as-is (default) |
| `reword` | `r` | Use the commit but open editor to change the message |
| `edit` | `e` | Pause at this commit so you can amend files or split it |
| `squash` | `s` | Meld this commit into the one above it; combine both messages |
| `fixup` | `f` | Meld this commit into the one above it; discard this message |
| `drop` | `d` | Remove this commit entirely from history |
| `exec` | `x` | Run a shell command at this point in the replay |
| `break` | `b` | Pause here; resume with `git rebase --continue` |

**The golden rule:** Never rebase commits that have already been pushed to a shared branch. Rebase rewrites commit hashes; if colleagues have based work on the old hashes, their history diverges. Rebase freely on feature branches you own; use `git revert` on shared branches.

#### Squashing a Noisy Feature Branch

The most common use case: you made ten "WIP" commits while developing a feature and want to present the work as two clean commits before merging.

```bash
# Open the last 10 commits in the interactive editor
git rebase -i HEAD~10
```

The editor opens with content like:

```
pick 1a2b3c4 WIP: start auth module
pick 2b3c4d5 WIP: add password hashing
pick 3c4d5e6 Fix typo
pick 4d5e6f7 WIP: add JWT generation
pick 5e6f7a8 debug logging (remove later)
pick 6f7a8b9 WIP: add refresh tokens
pick 7a8b9c0 remove debug logging
pick 8b9c0d1 WIP: validation
pick 9c0d1e2 Add tests for auth
pick 0d1e2f3 Final cleanup
```

Edit to:

```
pick 1a2b3c4 WIP: start auth module
squash 2b3c4d5 WIP: add password hashing
squash 3c4d5e6 Fix typo
squash 4d5e6f7 WIP: add JWT generation
fixup 5e6f7a8 debug logging (remove later)
squash 6f7a8b9 WIP: add refresh tokens
fixup 7a8b9c0 remove debug logging
squash 8b9c0d1 WIP: validation
pick 9c0d1e2 Add tests for auth
squash 0d1e2f3 Final cleanup
```

Git replays the commits. For each `squash`, it opens an editor letting you combine the messages. For each `fixup`, it silently discards the message. The result is two clean commits.

#### Using --autosquash to Automate Fixups

When you know during a working session that a new commit fixes a previous one, create it with `--fixup`:

```bash
# Your original commit
git commit -m "Add user registration endpoint"

# Later, you discover a bug in that commit and fix it
git add src/auth.js
git commit --fixup HEAD~3
# Git automatically names this commit: "fixup! Add user registration endpoint"
```

When you later run interactive rebase with `--autosquash`, Git automatically moves the fixup commit directly below its target and marks it as `fixup` — no manual editor work required:

```bash
git rebase -i --autosquash HEAD~5
```

#### Editing a Commit to Split It

When a commit does too many things at once, use `edit` to pause the rebase and split it:

```bash
git rebase -i HEAD~3
# Change "pick" to "edit" on the oversized commit, save and close
```

Git pauses after applying that commit. You then undo it (keeping the changes in your working directory) and re-commit in logical pieces:

```bash
# Undo the commit, keep all changes staged
git reset HEAD^

# Stage and commit only the first logical change
git add src/models/user.js
git commit -m "Add User model with validation"

# Stage and commit the second logical change
git add src/routes/users.js
git commit -m "Add user REST endpoints"

# Resume the rebase
git rebase --continue
```

If anything goes wrong at any point, `git rebase --abort` returns the repository to its state before the rebase started.

---

### git cherry-pick — Applying Specific Commits Across Branches

`git cherry-pick` applies one or more commits from anywhere in the repository to the current branch, creating new commits with the same changes but different hashes.

```bash
# Apply a single commit by its hash
git cherry-pick a1b2c3d

# Apply a range of commits (inclusive of both endpoints)
git cherry-pick a1b2c3d..e4f5a6b

# Apply multiple non-contiguous commits
git cherry-pick a1b2c3d e4f5a6b f6a7b8c

# Cherry-pick without committing (stage only, review before committing)
git cherry-pick --no-commit a1b2c3d

# Preserve the original author metadata in the new commit
git cherry-pick -x a1b2c3d
```

The `-x` flag appends "(cherry picked from commit ...)" to the commit message, which is useful for audit trails in long-lived release branches.

**When cherry-pick produces a conflict**, Git pauses and marks the conflict in the usual way. After resolving:

```bash
# After resolving conflicts manually
git add src/fixed-file.js
git cherry-pick --continue

# Or abort the entire operation
git cherry-pick --abort
```

**Typical use cases:**

- **Backporting a bug fix** to an older release branch: `main` has a critical security fix at hash `a1b2c3d` and you need it on `release/2.4` without merging all of `main`.
- **Salvaging work from a discarded branch**: A feature branch was abandoned, but one utility function added to it is genuinely useful on `main`.
- **Applying a hotfix to multiple release branches simultaneously**: Cherry-pick the fix from `hotfix/cve-123` onto `release/2.4`, `release/2.5`, and `main`.

Cherry-pick should be used deliberately. If you find yourself cherry-picking many commits between two branches, a merge or rebase is almost always the cleaner solution.

---

### git bisect — Binary Search for Bug-Introducing Commits

`git bisect` automates the process of finding which commit introduced a regression. Instead of manually checking out commits one by one, Git uses a binary search: with each round of testing, it eliminates half of the remaining candidates. Finding the culprit in a range of 1,000 commits takes at most 10 rounds.

#### Manual Bisect Workflow

```bash
# Start a bisect session
git bisect start

# Mark the current state as broken
git bisect bad

# Mark a known-good commit (tag, branch name, or hash all work)
git bisect good v2.1.0

# Git checks out the midpoint commit and tells you how many are left:
# "Bisecting: 42 revisions left to test after this (roughly 5 steps)"
```

Test whether the checked-out commit exhibits the bug. Then report to Git:

```bash
git bisect good   # This commit does NOT have the bug
# or
git bisect bad    # This commit DOES have the bug
```

Repeat until Git announces:

```
b047b02ea83310a70fd603dc8cd7a6cd13d15c04 is the first bad commit
commit b047b02ea83310a70fd603dc8cd7a6cd13d15c04
Author: Dev Name <dev@example.com>
Date:   Tue Jan 14 10:32:15 2025 -0800

    Refactor payment processor to use new gateway API
```

Always end the session to return HEAD to its original position:

```bash
git bisect reset
```

#### Automated Bisect with a Test Script

If you have a test or script that returns exit code 0 for a good state and non-zero for a bad one, you can fully automate the bisect:

```bash
git bisect start HEAD v2.1.0
git bisect run ./scripts/check-regression.sh
```

Git runs the script at each midpoint, records the result, and announces the first bad commit without any further interaction. This is especially powerful in CI-adjacent workflows where the test suite can be re-run against any commit.

```bash
# Using the test suite directly (requires a fast build)
git bisect start HEAD v2.1.0
git bisect run npm test -- --testPathPattern="PaymentProcessor"
```

After `git bisect run` finishes, always call `git bisect reset` to clean up.

---

### git reflog — Your Safety Net for Lost Commits

Every time HEAD moves — through a commit, checkout, reset, rebase, or merge — Git appends an entry to the **reflog** (reference log). The reflog is stored locally and is never shared with remotes. Entries expire after 90 days by default, but within that window no commit is truly lost.

```bash
# View the HEAD reflog (most recent first)
git reflog

# View the reflog for a specific branch
git reflog show feature/auth

# Show reflog with timestamps
git reflog --date=iso
```

Typical output:

```
a3f9c12 (HEAD -> main) HEAD@{0}: commit: Add password validation
7b2e4a1 HEAD@{1}: reset: moving to HEAD~1
9c0d1e2 HEAD@{2}: commit: Add email validation
3c1a8f0 HEAD@{3}: checkout: moving from feature/auth to main
```

Each entry has a reference of the form `HEAD@{N}` where N is the number of moves ago.

#### Recovering from a Destructive Reset

The most common reflog rescue scenario: you ran `git reset --hard` and lost commits you needed.

```bash
# Oh no — you reset too far
git reset --hard HEAD~3

# Find where HEAD was before the reset
git reflog
# Output shows: 9c0d1e2 HEAD@{1}: commit: Add email validation

# Restore the branch to that state
git reset --hard HEAD@{1}
# or equivalently
git reset --hard 9c0d1e2
```

#### Recovering a Deleted Branch

If you deleted a branch that had unmerged commits, the commits are still reachable via the reflog:

```bash
# Find the last commit that was on the deleted branch
git reflog
# Identify the hash: e.g., 5a6b7c8 HEAD@{4}: commit: Final feature work

# Recreate the branch pointing to that commit
git branch feature/auth-recovered 5a6b7c8
```

---

### git reset vs. git revert vs. git restore

These three commands sound similar and are frequently confused. Each operates on a different scope and has different implications for shared history.

#### git reset — Move the Branch Pointer

`git reset` moves the current branch pointer to a specified commit, optionally adjusting the staging area and working directory to match.

```bash
# --soft: Move the branch pointer only; staged changes and working files untouched
# Use when: You want to recommit with a different message, or squash N commits manually
git reset --soft HEAD~1

# --mixed (default): Move branch pointer AND clear the staging area; working files untouched
# Use when: You want to unstage changes without losing the edited files
git reset HEAD~1
git reset --mixed HEAD~1   # identical to above

# --hard: Move branch pointer, clear staging area, AND reset working files
# Use when: You want to completely discard commits and all associated changes
# WARNING: Uncommitted work in the working directory is permanently lost
git reset --hard HEAD~1

# Unstage a specific file without touching the commit or working file
git reset HEAD path/to/file.js
```

**Summary table:**

| Flag | Moves branch pointer | Clears staging area | Resets working files | Safe? |
|------|---------------------|--------------------|--------------------|-------|
| `--soft` | Yes | No | No | Yes |
| `--mixed` | Yes | Yes | No | Yes |
| `--hard` | Yes | Yes | Yes | No — data loss possible |

**Critical rule:** Only use `git reset` on commits that have not been pushed to a shared remote. Resetting pushed commits rewrites history and forces collaborators into a broken state.

#### git revert — Create an Undo Commit

`git revert` creates a new commit that inverts the changes introduced by a specified commit. The original commit remains in history; nothing is rewritten.

```bash
# Revert the most recent commit
git revert HEAD

# Revert a specific commit by hash
git revert a1b2c3d

# Revert a range of commits (each gets its own revert commit)
git revert a1b2c3d..e4f5a6b

# Revert without immediately committing (review changes first)
git revert --no-commit a1b2c3d
```

`git revert` is the correct tool for undoing work on `main`, `develop`, or any branch that other people have pulled. It is safe because it only appends to history rather than rewriting it.

#### git restore — Discard Changes in Files

`git restore` (introduced in Git 2.23 as part of the `git checkout` decomposition) operates on file content only — it does not move branch pointers.

```bash
# Discard unstaged changes to a file, reverting it to the staged version
git restore src/app.js

# Discard all unstaged changes in the current directory
git restore .

# Unstage a file (move it from staging area back to working directory only)
git restore --staged src/app.js

# Restore a file to its state at a specific commit (affects working tree and staging area)
git restore --source=HEAD~2 src/app.js
```

#### Decision Guide

| Situation | Correct command |
|-----------|----------------|
| Undo a commit on a shared branch (main, develop) | `git revert` |
| Undo local commits before pushing | `git reset --soft` or `git reset --mixed` |
| Completely discard local commits AND file changes | `git reset --hard` |
| Discard unsaved edits to a file | `git restore <file>` |
| Unstage a file without losing the edits | `git restore --staged <file>` |

---

### git tag — Marking Releases with Semantic Versioning

Tags are permanent, named pointers to specific commits. Unlike branches, tags do not advance when new commits are added. They exist to mark milestones — most commonly release versions.

#### Lightweight vs. Annotated Tags

**Lightweight tags** are simply a named pointer to a commit. They store no metadata.

```bash
git tag v1.4-lw
```

**Annotated tags** are stored as full objects in the Git database. They record the tagger's name, email, date, and a message. They can be signed with GPG. Annotated tags are the standard for release tagging.

```bash
# Create an annotated tag on the current commit
git tag -a v1.4.0 -m "Release v1.4.0: add OAuth2 support and fix session leaks"

# Tag a past commit by hash
git tag -a v1.3.1 -m "Backport security patch" 9fceb02

# View tag metadata
git show v1.4.0
```

#### Listing and Filtering Tags

```bash
# List all tags in alphabetical order
git tag

# List tags matching a glob pattern
git tag -l "v1.8.*"

# List tags sorted by semantic version (Git 2.12+)
git tag -l --sort=-version:refname "v*"
```

#### Pushing and Deleting Tags

Tags are not pushed automatically. You must push them explicitly:

```bash
# Push a single tag
git push origin v1.4.0

# Push all tags (avoid --tags if possible; it pushes lightweight tags too)
git push origin --follow-tags   # Push only annotated tags reachable from current branch
```

To delete:

```bash
# Delete locally
git tag -d v1.4.0-rc1

# Delete from remote
git push origin --delete v1.4.0-rc1
```

#### Semantic Versioning with Git Tags

Semantic versioning (SemVer) defines version numbers as `MAJOR.MINOR.PATCH`:

- **PATCH** (`v1.4.1`): Backward-compatible bug fixes
- **MINOR** (`v1.5.0`): New backward-compatible features
- **MAJOR** (`v2.0.0`): Breaking changes

Pre-release identifiers and build metadata are also valid: `v2.0.0-beta.1`, `v2.0.0-rc.2`.

A standard release workflow using tags:

```bash
# 1. Finish the release on the release branch
git checkout release/2.0.0
git merge --no-ff feature/oauth2

# 2. Tag the release commit on main after merging
git checkout main
git merge --no-ff release/2.0.0
git tag -a v2.0.0 -m "Release v2.0.0: OAuth2 support, breaks v1.x config format"

# 3. Push the branch and the tag
git push origin main
git push origin v2.0.0

# 4. Delete the release branch
git branch -d release/2.0.0
git push origin --delete release/2.0.0
```

To check out tagged code (read-only review):

```bash
git checkout v1.4.0
# HEAD is now in detached state

# To make commits based on a tag, create a branch first
git checkout -b hotfix/1.4.1 v1.4.0
```

---

### git submodules — Embedding External Repositories

A Git submodule is a full Git repository nested inside another repository. The parent repository records a pointer to a specific commit in the submodule, not a copy of its files. This makes submodules appropriate for: including a shared internal library, embedding a dependency you need to modify, or building a monorepo-style layout where multiple services each live in their own repository but are deployed together.

#### Adding a Submodule

```bash
# Add a submodule at the default path (directory named after the repo)
git submodule add https://github.com/example/shared-utils

# Add at a custom path
git submodule add https://github.com/example/shared-utils lib/utils
```

This creates two things: the submodule directory and a `.gitmodules` file:

```ini
[submodule "lib/utils"]
    path = lib/utils
    url = https://github.com/example/shared-utils
```

Both the `.gitmodules` file and the submodule directory entry must be committed to record the submodule in the parent repository:

```bash
git add .gitmodules lib/utils
git commit -m "Add shared-utils as submodule at lib/utils"
```

#### Cloning a Repository That Has Submodules

```bash
# Clone and initialize all submodules in one step (recommended)
git clone --recurse-submodules https://github.com/example/parent-repo

# If you already cloned without --recurse-submodules, initialize afterward
git submodule update --init --recursive
```

#### Updating a Submodule to a New Upstream Commit

```bash
# Update all submodules to the latest commit on their tracked branch
git submodule update --remote

# Update a specific submodule only
git submodule update --remote lib/utils

# Configure a submodule to track a specific branch
git config -f .gitmodules submodule.lib/utils.branch main
git submodule update --remote --merge
```

After updating, the parent repository sees that the submodule pointer has changed. You must commit this change in the parent:

```bash
git add lib/utils
git commit -m "Update shared-utils submodule to latest main"
```

#### Running Commands Across All Submodules

```bash
# Stash all submodule changes before a risky operation
git submodule foreach 'git stash'

# Check the status of every submodule
git submodule foreach 'git status'

# Restore all submodule stashes
git submodule foreach 'git stash pop'
```

#### Removing a Submodule

Removing a submodule requires touching three places: the `.gitmodules` file, the `.git/config` file, and the repository index.

```bash
# 1. Remove the submodule entry from .gitmodules
git config -f .gitmodules --remove-section submodule.lib/utils

# 2. Stage the .gitmodules change
git add .gitmodules

# 3. Remove the submodule from the index (do NOT use rm -rf on the directory first)
git rm --cached lib/utils

# 4. Remove the submodule directory from the working tree
rm -rf lib/utils

# 5. Remove the submodule's entry from .git/config
git config --remove-section submodule.lib/utils

# 6. Remove the gitdir for the submodule
rm -rf .git/modules/lib/utils

# 7. Commit the removal
git commit -m "Remove shared-utils submodule"
```

---

### git worktree — Multiple Branches Simultaneously

`git worktree` lets you check out different branches of the same repository into separate directories on disk simultaneously, without cloning. All worktrees share a single `.git` directory, so they also share the same stash, reflog, and configuration.

The classic use case: you are deep in refactoring work on `feature/refactor` when an urgent production bug is reported. Without worktrees, you must stash your changes, switch branches, fix the bug, commit, switch back, and unstash. With worktrees, you simply open a second terminal window in a parallel directory.

```bash
# Add a new worktree on an existing branch
git worktree add ../hotfix-workspace hotfix/critical-bug

# Add a new worktree and create a new branch at the same time
git worktree add -b emergency-fix ../emergency-fix-workspace main

# List all active worktrees
git worktree list
```

Example output of `git worktree list`:

```
/home/user/project         a3f9c12 [feature/refactor]
/home/user/emergency-fix   a3f9c12 [emergency-fix]
```

Work in the new worktree directory independently:

```bash
cd ../emergency-fix-workspace

# Make the fix, commit, push
git add src/payment.js
git commit -m "Fix null dereference in payment processor"
git push origin emergency-fix

# Return to the main worktree
cd ../project
# Your refactoring work is exactly as you left it
```

When you are finished with the additional worktree:

```bash
# Remove a worktree (fails if it has uncommitted changes)
git worktree remove ../emergency-fix-workspace

# Force-remove if needed
git worktree remove --force ../emergency-fix-workspace

# Prune stale worktree metadata (e.g., directory was deleted manually)
git worktree prune
```

**Constraints:** A branch can only be checked out in one worktree at a time. Attempting to `git worktree add` for a branch that is already checked out in another worktree produces an error. Submodule support in linked worktrees is incomplete as of Git 2.53; initialize submodules separately in each worktree with `git submodule update --init`.

---

### Git Hooks — Automating Quality Enforcement

A Git hook is an executable script placed in `.git/hooks/` that Git calls at specific points in its operation. Hooks run on the local machine and are not versioned — they are not copied when someone clones the repository. To share hooks with a team, commit them to a directory like `.githooks/` in the repository and configure Git to use that directory:

```bash
git config core.hooksPath .githooks
```

Hooks must be executable. On Linux/macOS:

```bash
chmod +x .githooks/pre-commit
```

On Windows with Git for Windows, hook scripts must use a Unix-style shebang line and be executable via the Git Bash environment.

#### pre-commit

Runs before Git opens the editor for a commit message. If the hook exits with a non-zero code, the commit is aborted. Used to enforce code style, run linters, or prevent committing debug artifacts.

```bash
#!/bin/sh
# .githooks/pre-commit
# Abort the commit if any staged JavaScript files fail ESLint

STAGED_JS=$(git diff --cached --name-only --diff-filter=ACM | grep '\.js$')

if [ -n "$STAGED_JS" ]; then
    echo "$STAGED_JS" | xargs npx eslint --max-warnings=0
    if [ $? -ne 0 ]; then
        echo "pre-commit: ESLint found errors. Commit aborted."
        exit 1
    fi
fi

exit 0
```

To bypass the hook in exceptional circumstances:

```bash
git commit --no-verify -m "WIP: skip lint check"
```

#### commit-msg

Runs after the commit message is written but before the commit is finalized. Receives the path to a temporary file containing the message as its first argument. Use it to enforce a commit message convention.

```bash
#!/bin/sh
# .githooks/commit-msg
# Enforce Conventional Commits format: type(scope): description
# Examples: feat(auth): add OAuth2 login, fix(api): handle null response

MSG_FILE="$1"
MSG=$(cat "$MSG_FILE")
PATTERN='^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\(.+\))?: .{1,72}$'

if ! echo "$MSG" | grep -qE "$PATTERN"; then
    echo "commit-msg: Commit message does not follow Conventional Commits format."
    echo "  Expected: type(scope): description"
    echo "  Example:  feat(auth): add password reset flow"
    echo "  Received: $MSG"
    exit 1
fi

exit 0
```

#### pre-push

Runs during `git push`, after the remote refs are identified but before any data is transferred. If it exits non-zero, the push is aborted. Use it to prevent pushing to protected branches, ensure tests pass before pushing, or block large binary files.

```bash
#!/bin/sh
# .githooks/pre-push
# Block direct pushes to main or develop

REMOTE="$1"
REFSPECS=$(cat)

while read local_ref local_sha remote_ref remote_sha; do
    if echo "$remote_ref" | grep -qE '^refs/heads/(main|develop)$'; then
        echo "pre-push: Direct push to $(echo $remote_ref | sed 's|refs/heads/||') is not allowed."
        echo "  Please open a pull request instead."
        exit 1
    fi
done <<< "$REFSPECS"

exit 0
```

**Common hook use cases summary:**

| Hook | Fires when | Typical use |
|------|-----------|-------------|
| `pre-commit` | Before message editor opens | Linting, formatting, secret detection |
| `commit-msg` | After message is written | Enforce message conventions |
| `pre-push` | Before data transfer to remote | Block protected branches, run tests |
| `post-commit` | After commit completes | Notifications, local CI triggers |
| `post-checkout` | After `git checkout` / `git switch` | Rebuild dependencies, update config |

---

### Advanced Log, Diff, and Blame

#### git log — Graph and Custom Formats

The full branch topology of a repository, including all remote-tracking branches, is visible with:

```bash
git log --oneline --graph --all --decorate
```

For a more informative one-liner customized with color and alignment:

```bash
git log --graph --pretty=format:'%C(yellow)%h%Creset -%C(red)%d%Creset %s %C(green)(%ar)%Creset %C(blue)[%an]%Creset' --abbrev-commit --all
```

Useful `--pretty=format` placeholders:

| Placeholder | Value |
|------------|-------|
| `%h` | Abbreviated commit hash |
| `%H` | Full commit hash |
| `%s` | Subject (first line of message) |
| `%an` | Author name |
| `%ae` | Author email |
| `%ar` | Author date, relative (e.g., "3 days ago") |
| `%ci` | Committer date, ISO 8601 |
| `%d` | Ref names (branches, tags) |

Save a frequently-used format as an alias:

```bash
git config --global alias.lg "log --graph --pretty=format:'%C(yellow)%h%Creset -%C(red)%d%Creset %s %C(green)(%ar)%Creset %C(blue)[%an]%Creset' --abbrev-commit --all"
git lg
```

Filtering log output:

```bash
# All commits by a specific author in the last 30 days
git log --author="Alice" --since="30 days ago" --oneline

# All commits that touched a specific file, following renames
git log --follow -- src/legacy/oldname.js

# All commits whose message contains a string
git log --grep="security" --oneline

# All commits that added or removed a specific string in a file's content
git log -S "function calculateTax" --oneline

# All commits between two tags
git log v1.3.0..v1.4.0 --oneline
```

#### git shortlog — Contribution Summaries

`git shortlog` groups commits by author and is used to generate release changelogs and contribution summaries:

```bash
# Summary: count of commits per author
git shortlog -sn

# All commits since last tag, grouped by author
git shortlog v1.3.0..HEAD

# Summary of commits since last tag (useful for release notes)
git shortlog -sn v1.3.0..HEAD
```

#### git blame — Line-Level Attribution

`git blame` annotates each line of a file with the commit hash, author, and date of the last modification to that line:

```bash
# Annotate an entire file
git blame src/auth.js

# Annotate a specific line range
git blame -L 45,72 src/auth.js

# Ignore whitespace-only changes
git blame -w src/auth.js

# Track code that was moved or copied from another file in the same commit
git blame -C src/auth.js

# Track code movement across multiple commits
git blame -C -C -C src/auth.js
```

When `git blame` shows a commit that is a refactor (the code moved but was not changed), use `git log -p <hash>` to read the original commit that introduced the logic, then trace backward from there.

#### Advanced git diff

```bash
# Word-level diff instead of line-level (easier to read for prose or config changes)
git diff --word-diff

# Diff with function context showing the enclosing function name
git diff --function-context src/auth.js

# Statistical summary: files changed, insertions, deletions
git diff --stat main feature/auth

# Check if there is any difference without showing it (useful in scripts)
git diff --quiet main feature/auth
echo "Exit code: $?"   # 0 = identical, 1 = differences exist
```

---

## Best Practices

1. **Treat interactive rebase as a publishing step, not a daily habit.** Run `git rebase -i` once before opening a pull request to clean up your feature branch history. Never run it on commits already on a shared branch.

2. **Prefer `git revert` over `git reset --hard` on shared branches.** Reverting preserves the audit trail and keeps other developers' local copies valid. A hard reset on a pushed branch forces everyone to run `git reset --hard origin/main`, which is disruptive and error-prone.

3. **Always run `git bisect reset` after a bisect session.** Forgetting leaves HEAD pointing at a detached midpoint commit, which confuses status output and can lead to commits being made on no branch.

4. **Use annotated tags exclusively for releases.** Annotated tags record who tagged, when, and why. Lightweight tags are appropriate only for personal, temporary bookmarks that will never be pushed.

5. **Push tags explicitly with `--follow-tags`, not `--tags`.** The `--tags` flag pushes all tags including lightweight ones. `--follow-tags` pushes only annotated tags that are reachable from the current branch, which matches the intent of a release workflow.

6. **Commit changes to submodule pointers immediately.** Leaving a dirty submodule pointer uncommitted in the parent repository confuses teammates who fetch the parent: their submodule will be at a different commit than yours, silently.

7. **Store hooks in a committed directory and configure `core.hooksPath`.** The `.git/hooks/` directory is not versioned. Any enforcement you build into hooks is meaningless if teammates have different or no hooks. Committing hooks to `.githooks/` and running `git config core.hooksPath .githooks` in project setup scripts ensures consistent enforcement.

8. **Know the reflog expiry.** The default expiry for reachable objects is 90 days and for unreachable objects is 30 days. If you need to recover something older, check whether you have a remote copy or a stash. Do not rely on the reflog indefinitely.

9. **Use `git worktree` instead of multiple clones.** Multiple clones of the same repository consume more disk space and do not share stash or reflog. Linked worktrees share a single `.git` directory and are more efficient for parallel branch work.

10. **Use `git log -S` to find where functionality was introduced or removed.** When debugging regressions, `git log -S "keyFunctionName"` is often faster than `git bisect` if you already know what code changed — it directly shows the commits that added or removed that string.

---

## Use Cases

### Use Case 1: Cleaning a Feature Branch Before a Pull Request

A developer has made 14 commits over three days, including "WIP" saves, typo fixes, and debug logging commits. The team's PR policy requires a clean, logical commit history.

- **Problem:** The raw commit log is too noisy for reviewers to follow the intent of the changes, and it will pollute `main`'s history permanently once merged.
- **Concepts applied:** `git rebase -i HEAD~14`, `squash`, `fixup`, `reword`
- **Expected outcome:** Three logical commits — one for the data model changes, one for the API endpoints, one for the tests — each with a clear, imperative commit message. The feature branch is then force-pushed to the PR branch and the review can proceed.

### Use Case 2: Backporting a Security Fix to an Older Release

A critical authentication bypass is fixed on `main`. The project maintains `release/3.1` and `release/2.9` for enterprise customers who cannot upgrade immediately.

- **Problem:** The fix on `main` involves several commits interleaved with unrelated features; a full merge would bring unwanted changes into the old release branches.
- **Concepts applied:** `git cherry-pick -x <hash>`, conflict resolution, `git push origin release/3.1`
- **Expected outcome:** The exact fix commits (and no others) are applied to each release branch. The `-x` flag traces the origin in case future auditors need to verify the backport.

### Use Case 3: Finding the Commit That Broke the Login Flow

After a two-week sprint, QA reports that user login stopped working. The last known-good state was the `v3.2.0` tag, 120 commits ago.

- **Problem:** Manually checking out and testing 120 commits is impractical. The regression could be in any of the dozens of files modified across those commits.
- **Concepts applied:** `git bisect start`, `git bisect good v3.2.0`, `git bisect bad`, `git bisect run npm test -- --testPathPattern=Login`, `git bisect reset`
- **Expected outcome:** Git identifies the exact culprit commit in approximately 7 rounds of automated testing. The developer can read the diff of that commit to understand the root cause and write a targeted fix.

### Use Case 4: Recovering Work Lost After a Mistaken Reset

A developer intended to run `git reset --soft HEAD~1` to recommit with a better message but instead ran `git reset --hard HEAD~3`, discarding three commits and all working directory changes.

- **Problem:** Three days of work appear gone. `git log` does not show the commits.
- **Concepts applied:** `git reflog`, `git reset --hard HEAD@{1}`
- **Expected outcome:** The reflog shows the state before the reset. The developer restores the branch to that state in under a minute, losing nothing.

### Use Case 5: Enforcing Conventional Commits Across a Team

A team has adopted Conventional Commits for automated changelog generation. Developers occasionally forget the format and push non-conformant messages, breaking the changelog tool.

- **Problem:** There is no automated enforcement; the team relies on manual code review to catch bad messages, which is inconsistent.
- **Concepts applied:** `commit-msg` hook validating against the Conventional Commits pattern, hooks committed to `.githooks/`, `git config core.hooksPath .githooks` in project setup
- **Expected outcome:** Any commit with a non-conformant message is rejected locally before it can reach the remote. The enforcement is consistent for every developer who runs the project setup script.

---

## Hands-on Examples

### Example 1: Interactive Rebase — Squash a Noisy Branch

You have been working on a feature and accumulated several work-in-progress commits. Before opening a pull request, you will squash them into two clean commits.

1. Set up the scenario with five messy commits.

```bash
mkdir rebase-demo
cd rebase-demo
git init -b main
git commit --allow-empty -m "Initial commit"

git checkout -b feature/cleanup-demo

echo "step 1" > app.txt
git add app.txt
git commit -m "WIP: start feature"

echo "step 2" >> app.txt
git add app.txt
git commit -m "WIP: more work"

echo "fix typo" >> app.txt
git add app.txt
git commit -m "fix typo"

echo "step 3" >> app.txt
git add app.txt
git commit -m "WIP: finishing touches"

echo "tests" > tests.txt
git add tests.txt
git commit -m "Add tests"
```

2. Verify the current log.

```bash
git log --oneline
```

Expected output (hashes will differ):

```
d4e5f6a (HEAD -> feature/cleanup-demo) Add tests
c3d4e5f WIP: finishing touches
b2c3d4e fix typo
a1b2c3d WIP: more work
9z0a1b2 WIP: start feature
8y9z0a1 (main) Initial commit
```

3. Launch the interactive rebase for the last five commits.

```bash
git rebase -i HEAD~5
```

4. The editor opens. Edit it to look like this (using the actual hashes shown in your editor), then save and close:

```
pick 9z0a1b2 WIP: start feature
squash a1b2c3d WIP: more work
squash b2c3d4e fix typo
squash c3d4e5f WIP: finishing touches
pick d4e5f6a Add tests
```

5. A second editor opens to combine the messages for the first four commits. Replace the auto-generated content with a single clean message:

```
Implement feature: multi-step app flow
```

Save and close.

6. Verify the result.

```bash
git log --oneline
```

Expected output:

```
e5f6a7b (HEAD -> feature/cleanup-demo) Add tests
d4e5f6a Implement feature: multi-step app flow
8y9z0a1 (main) Initial commit
```

The five noisy commits are now two clean ones, ready for review.

---

### Example 2: git bisect — Find a Regression Automatically

You will simulate a regression across several commits, then use `git bisect run` to locate it.

1. Create the repository with a history of commits, one of which introduces a bug.

```bash
mkdir bisect-demo
cd bisect-demo
git init -b main

echo 'exit 0' > check.sh
chmod +x check.sh
git add check.sh
git commit -m "v1.0: initial good state"

git commit --allow-empty -m "v1.1: minor change A"
git commit --allow-empty -m "v1.2: minor change B"

# Introduce the bug in v1.3
echo 'exit 1' > check.sh
git add check.sh
git commit -m "v1.3: refactor (contains bug)"

git commit --allow-empty -m "v1.4: minor change C"
git commit --allow-empty -m "v1.5: minor change D"
```

2. Record the known-good tag and observe the current failing state.

```bash
git tag v1.0 HEAD~5
./check.sh
echo "Exit code: $?"   # Should be 1 (bad)
```

3. Run bisect automatically.

```bash
git bisect start HEAD v1.0
git bisect run ./check.sh
```

Expected output (hashes will differ):

```
Bisecting: 2 revisions left to test after this (roughly 2 steps)
[<hash>] v1.2: minor change B
running ./check.sh
Bisecting: 0 revisions left to test after this (roughly 1 step)
[<hash>] v1.3: refactor (contains bug)
running ./check.sh
<hash> is the first bad commit
commit <hash>
    v1.3: refactor (contains bug)
bisect found first bad commit
```

4. Clean up.

```bash
git bisect reset
```

HEAD returns to `HEAD` (the tip of `main`).

---

### Example 3: git reflog — Recover a Hard-Reset Disaster

You will simulate a destructive `git reset --hard` and then recover the lost commits using the reflog.

1. Set up a repository with three commits.

```bash
mkdir reflog-demo
cd reflog-demo
git init -b main

echo "commit one" > history.txt
git add history.txt
git commit -m "Commit one"

echo "commit two" >> history.txt
git add history.txt
git commit -m "Commit two"

echo "commit three" >> history.txt
git add history.txt
git commit -m "Commit three"
```

2. Record the current log, then simulate a mistake.

```bash
git log --oneline
# Output: three commits visible

# MISTAKE: you intended HEAD~1 but typed HEAD~3
git reset --hard HEAD~3

git log --oneline
# Output: "No commits yet" — looks like everything is gone
```

3. Use the reflog to find the lost state.

```bash
git reflog
```

Expected output:

```
0000000 (HEAD -> main) HEAD@{0}: reset: moving to HEAD~3
a3f9c12 HEAD@{1}: commit: Commit three
7b2e4a1 HEAD@{2}: commit: Commit two
3c1a8f0 HEAD@{3}: commit: Commit one
```

4. Restore the branch to the state before the reset.

```bash
git reset --hard HEAD@{1}

git log --oneline
```

Expected output:

```
a3f9c12 (HEAD -> main) Commit three
7b2e4a1 Commit two
3c1a8f0 Commit one
```

All three commits are recovered.

---

### Example 4: Creating and Pushing an Annotated Release Tag

You have a repository with completed features and want to mark the `v1.0.0` release.

1. Confirm you are on the correct branch and everything is committed.

```bash
git checkout main
git log --oneline -5
git status
```

2. Create an annotated tag.

```bash
git tag -a v1.0.0 -m "Release v1.0.0: initial public release with user auth and task management"
```

3. Inspect the tag object.

```bash
git show v1.0.0
```

Expected output includes the tagger metadata, the message, and the tagged commit information.

4. Push the tag to the remote.

```bash
git push origin --follow-tags
```

Expected output includes:

```
 * [new tag]         v1.0.0 -> v1.0.0
```

5. List all tags.

```bash
git tag -l --sort=-version:refname
```

Expected output:

```
v1.0.0
```

---

### Example 5: Writing a pre-commit Hook That Blocks Debug Statements

You want to prevent `console.log` and `debugger` statements from being committed to any JavaScript file.

1. Create the hooks directory and the hook script.

```bash
mkdir -p .githooks

cat > .githooks/pre-commit << 'EOF'
#!/bin/sh
# Block console.log and debugger statements in staged JS files

STAGED_JS=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(js|ts)$')

if [ -z "$STAGED_JS" ]; then
    exit 0
fi

VIOLATIONS=$(echo "$STAGED_JS" | xargs grep -n "console\.log\|debugger" 2>/dev/null)

if [ -n "$VIOLATIONS" ]; then
    echo "pre-commit: Debug statements found in staged files:"
    echo "$VIOLATIONS"
    echo ""
    echo "Remove console.log and debugger statements before committing."
    echo "To bypass this check in emergencies: git commit --no-verify"
    exit 1
fi

exit 0
EOF

chmod +x .githooks/pre-commit
```

2. Configure Git to use the hooks directory.

```bash
git config core.hooksPath .githooks
```

3. Commit the hook to the repository so teammates get it.

```bash
git add .githooks/pre-commit
git commit -m "Add pre-commit hook: block console.log and debugger in JS/TS files"
```

4. Test the hook.

```bash
echo 'console.log("testing");' > test.js
git add test.js
git commit -m "Test the hook"
```

Expected output:

```
pre-commit: Debug statements found in staged files:
test.js:1:console.log("testing");

Remove console.log and debugger statements before committing.
To bypass this check in emergencies: git commit --no-verify
```

The commit is aborted. Clean up the file and the hook works as intended.

---

## Common Pitfalls

### Pitfall 1: Rebasing Commits That Have Already Been Pushed

**Description:** A developer runs `git rebase -i` on commits that are already on `origin/feature/auth`, then force-pushes. Teammates who have fetched that branch now have diverged histories and receive confusing errors on their next `git pull`.

**Why it happens:** The convenience of interactive rebase makes it tempting to clean up history even after pushing, without considering that others may have based work on those commits.

**Incorrect pattern:**
```bash
git push origin feature/auth           # Commits are now on the remote
git rebase -i HEAD~5                   # Rewrites hashes of those commits
git push --force origin feature/auth   # Overwrites remote history
# Teammates now have orphaned commits
```

**Correct pattern:**
```bash
# Rebase before the first push
git rebase -i HEAD~5
git push -u origin feature/auth

# If you must rebase after pushing (solo branch only), use --force-with-lease
# to abort if someone else has pushed to the branch since your last fetch
git push --force-with-lease origin feature/auth
```

---

### Pitfall 2: Using git reset --hard on a Shared Branch

**Description:** A developer wants to undo a bad commit on `main` and runs `git reset --hard HEAD~1` followed by `git push --force`. This rewrites public history and discards any commits teammates have pushed since then.

**Why it happens:** `git reset --hard` is the most direct way to undo something locally, and developers apply it to shared branches without considering the consequences.

**Incorrect pattern:**
```bash
git checkout main
git reset --hard HEAD~1      # Removes a commit
git push --force origin main  # DANGER: rewrites shared history
```

**Correct pattern:**
```bash
git checkout main
git revert HEAD              # Creates a new commit that undoes the last one
git push origin main         # Safe: appends to history, no force required
```

---

### Pitfall 3: Forgetting git bisect reset

**Description:** After a bisect session, the developer forgets to run `git bisect reset`. HEAD is left pointing at a detached commit somewhere in the middle of history. When they later commit, the commit goes on no branch and becomes unreachable.

**Why it happens:** The bisect session returns useful output (the first bad commit) and developers close the terminal, assuming Git cleaned up automatically.

**Incorrect pattern:**
```bash
git bisect start HEAD v1.0
git bisect run ./test.sh
# Git announces the bad commit — developer reads it, closes terminal
# HEAD is now detached at a midpoint commit
git commit -m "Fix the bug"   # This commit is on no branch
```

**Correct pattern:**
```bash
git bisect start HEAD v1.0
git bisect run ./test.sh
# Git announces the bad commit
git bisect reset              # Always clean up before doing anything else
git checkout -b fix/regression
git commit -m "Fix the regression introduced in <hash>"
```

---

### Pitfall 4: Submodule Pointer Drift

**Description:** A developer updates a submodule locally (`git submodule update --remote`) but forgets to commit the updated pointer in the parent repository. Other developers who run `git pull` on the parent get the old submodule pointer and see a dirty submodule in their status.

**Why it happens:** The submodule directory appearing "changed" in `git status` looks like an ordinary working tree change, but developers often ignore it or do not understand what it means.

**Incorrect pattern:**
```bash
git submodule update --remote lib/utils
# lib/utils is now at a newer commit than what the parent records
git push origin main           # Parent still records the old submodule commit
# Teammates pull and get confusing "submodule out of sync" warnings
```

**Correct pattern:**
```bash
git submodule update --remote lib/utils
git add lib/utils
git commit -m "Update shared-utils submodule to latest main"
git push origin main
```

---

### Pitfall 5: Cherry-picking Instead of Merging When Commits Are Related

**Description:** A developer cherry-picks 15 commits from a feature branch into `main` because the feature branch also contains "not-ready" work. The cherry-picked commits create duplicate commits with different hashes. When the feature branch is eventually merged, Git sees the original commits as different from the cherry-picked ones and reapplies them, introducing duplicate changes and conflicts.

**Why it happens:** Cherry-pick feels surgical and controlled. Developers use it as a substitute for a partial merge without understanding the downstream merge complications.

**Incorrect pattern:**
```bash
# Feature branch has 20 commits; 15 are "ready"
git cherry-pick <hash1> <hash2> ... <hash15>   # Cherry-pick 15 commits to main
# Later, when the branch is merged, those 15 commits conflict with their cherry-picked copies
```

**Correct pattern:**
```bash
# Use feature flags to hide incomplete functionality, then merge the whole branch
# Or split the work into two branches from the start:
git checkout -b feature/ready-part main
# Move only the ready commits here
git checkout -b feature/not-yet main
# Keep the unfinished work here
# Merge feature/ready-part cleanly when it's done
```

---

### Pitfall 6: Not Committing the .githooks Directory

**Description:** A developer writes a useful pre-commit hook in `.git/hooks/pre-commit`, which enforces linting. When a teammate clones the repository, they get no hook because `.git/` is not versioned.

**Why it happens:** Developers test the hook locally, it works, and they assume it is part of the repository.

**Incorrect pattern:**
```bash
# Write hook directly in the unversioned .git/hooks/
vim .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
# Teammate clones the repo and has no hook; pushes unlinted code
```

**Correct pattern:**
```bash
# Write hooks in a versioned directory
mkdir -p .githooks
vim .githooks/pre-commit
chmod +x .githooks/pre-commit
git config core.hooksPath .githooks
git add .githooks/pre-commit
git commit -m "Add pre-commit hook: enforce ESLint"
# Document in README or setup script: run "git config core.hooksPath .githooks"
```

---

## Summary

- **Interactive rebase** (`git rebase -i`) is the primary tool for cleaning up local history before sharing. Use `squash`, `fixup`, and `reword` to turn messy working commits into polished, logical snapshots. The golden rule: never rebase commits already on a shared branch.
- **`git cherry-pick`** applies specific commits to a different branch without merging the entire source branch. It is ideal for backporting fixes to release branches but should not substitute for a proper merge when entire feature branches are involved.
- **`git bisect`** uses binary search to pinpoint the commit that introduced a regression. Automate it with `git bisect run` and a test script for O(log n) debugging, always finishing with `git bisect reset`.
- **`git reflog`** is your local safety net. Every HEAD movement is recorded. Lost commits from resets, deleted branches, and failed rebases are recoverable within the 90-day expiry window.
- **`git reset`**, **`git revert`**, and **`git restore`** serve distinct purposes: reset moves the branch pointer (local history only), revert creates an undo commit (safe for shared branches), and restore modifies file content without touching commits.
- **Annotated tags** mark release versions with full metadata. Combine them with semantic versioning (`vMAJOR.MINOR.PATCH`) and push with `--follow-tags` as part of every release workflow.
- **Submodules** embed external repositories as pinned commit pointers. Always commit the updated pointer after running `git submodule update --remote`, and use `--recurse-submodules` when cloning.
- **`git worktree`** enables simultaneous work on multiple branches by creating linked working trees that share a single `.git` directory — more efficient than multiple clones.
- **Git hooks** automate enforcement of code quality, commit message conventions, and push policies. Hooks must be committed to a versioned directory and activated with `core.hooksPath` to be effective for an entire team.
- **Advanced `git log`**, **`git blame`**, and **`git diff`** options — `--graph`, `--pretty=format`, `-S`, `--follow`, `-C` — transform the repository history from a raw list of commits into a navigable audit trail and debugging tool.

---

## Further Reading

- [Pro Git Book — Chapter 7: Git Tools (git-scm.com)](https://git-scm.com/book/en/v2/Git-Tools-Rewriting-History) — The authoritative, free reference covering interactive rebase, stashing, signing, submodules, and the reset demystified chapter that explains the three-tree model in full detail; essential reading for understanding how these commands work at the object level.
- [Pro Git Book — Customizing Git: Git Hooks (git-scm.com)](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks) — The official documentation for every client-side and server-side hook, including the full list of available hooks, their input/output contracts, and language-agnostic implementation guidance.
- [Pro Git Book — Git Basics: Tagging (git-scm.com)](https://git-scm.com/book/en/v2/Git-Basics-Tagging) — Complete reference for lightweight and annotated tags, tag sharing, deletion, and checking out tagged versions; pairs directly with the semantic versioning section of this module.
- [Pro Git Book — Git Tools: Submodules (git-scm.com)](https://git-scm.com/book/en/v2/Git-Tools-Submodules) — The most thorough available treatment of submodule workflows: cloning, updating, publishing, the `submodule foreach` command, and pitfalls around detached HEAD state in submodule directories.
- [git-worktree Official Documentation (git-scm.com)](https://git-scm.com/docs/git-worktree) — The official reference page for all `git worktree` subcommands including `add`, `list`, `remove`, `lock`, and `prune`, with full option flags and behavioral notes on branch exclusivity.
- [Recovering Lost Commits with git reflog — Graphite](https://graphite.com/guides/recovering-lost-commits-git-reflog) — A practitioner-oriented walkthrough of the most common reflog recovery scenarios: hard resets, deleted branches, and failed rebases, with annotated before-and-after command sequences.
- [Versioning with Git Tags and Conventional Commits — SEI CMU Blog](https://www.sei.cmu.edu/blog/versioning-with-git-tags-and-conventional-commits/) — A thorough exploration from the Software Engineering Institute of combining annotated tags with Conventional Commits and semantic-release tooling to fully automate version management and changelog generation.
- [Interactive Rebase: Beyond Squashing Commits — murtazaweb.com](https://murtazaweb.com/blog/2026-03-21-git-rebase-interactive-practical-uses/) — A recent (March 2026) practitioner guide covering real-world interactive rebase scenarios beyond simple squashing, including `exec` for running tests between commit replays and the `break` command for manual inspection points.
- [Git bisect Official Documentation (git-scm.com)](https://git-scm.com/docs/git-bisect) — The complete reference for `git bisect`, including the `run` automation protocol, `git bisect log` and `git bisect replay` for reproducibility, and the `terms` subcommand for using domain-specific good/bad vocabulary in bisect sessions.
