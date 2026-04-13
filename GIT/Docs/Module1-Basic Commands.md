# Module 1: Basic Commands
> Subject: GIT | Difficulty: Beginner | Estimated Time: 90 minutes

## Objective

After completing this module, you will be able to initialize and clone Git repositories, stage and commit changes, inspect repository state and history using `git status`, `git log`, and `git diff`, manage branches with `git branch` and `git checkout`, integrate changes via `git merge`, and synchronize work with remote repositories using `git remote`, `git push`, and `git pull`. You will have a working mental model of the Git staging area and be able to execute a complete solo development workflow from scratch.

## Prerequisites

- A computer with Git 2.40 or later installed (verify with `git --version`; current stable release is 2.53.0)
- Basic familiarity with the command line (navigating directories, creating files)
- A free account on GitHub, GitLab, or any Git hosting service is helpful for the remote sections but not required for local exercises
- No prior Git knowledge is assumed

## Key Concepts

### The Three-Tree Architecture

Git tracks your project across three distinct "trees" at all times: the **working directory**, the **staging area (index)**, and the **repository (commit history)**. Understanding the relationship between these three areas is the most important mental model in Git — almost every confusing situation you will encounter as a beginner comes from losing track of which tree you are operating on.

The **working directory** is simply the files you see on disk. Any edit you make in your editor changes the working directory. Git notices these changes but does not record them automatically.

The **staging area** is a preparation buffer. You explicitly move changes from the working directory into the staging area using `git add`. Think of it as an outbox: you curate exactly what will go into the next commit before sealing it.

The **repository** is the permanent history. When you run `git commit`, Git takes everything in the staging area and stores it as a new, immutable snapshot called a commit. That snapshot is linked to its parent, forming a chain back to the very first commit in the project.

```
Working Directory  -->  Staging Area  -->  Repository
      (edit)          (git add)         (git commit)
```

### git init and git clone — Starting a Repository

Every Git project begins in one of two ways: you create a new repository from scratch with `git init`, or you copy an existing one with `git clone`.

`git init` creates a hidden `.git/` directory inside the current folder. That directory holds the entire database of your project's history. Nothing outside it is touched. The default branch name is `main` in Git 2.28 and later; on older installations it may default to `master`.

```bash
# Create a new project directory and initialize a repository
mkdir my-project
cd my-project
git init
# Output: Initialized empty Git repository in /path/to/my-project/.git/

# Initialize with an explicit branch name
git init -b main
```

`git clone` downloads a full copy of an existing repository — every commit, every branch, every tag — and sets up a remote named `origin` pointing back to the source automatically.

```bash
# Clone a remote repository into a new directory
git clone https://github.com/example/repo.git

# Clone into a specific directory name
git clone https://github.com/example/repo.git my-local-name

# Clone a specific branch only
git clone --branch develop https://github.com/example/repo.git
```

### git status — Knowing Where You Stand

`git status` is your most-used command. It reports which files have changed in the working directory, which of those changes are staged, and what branch you are on. Running it frequently costs nothing and prevents many mistakes.

The output groups files into three categories: **Changes to be committed** (staged), **Changes not staged for commit** (modified but not staged), and **Untracked files** (new files Git has never seen). An untracked file will never appear in a commit until you explicitly stage it.

```bash
git status

# Compact one-line-per-file output
git status -s
```

Example output after editing an existing file and creating a new one:

```
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
        modified:   src/app.js

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        notes.txt

no changes added to commit (use "git add" and/or "git commit -a")
```

### git add — Staging Changes

`git add` moves changes from the working directory into the staging area. You can stage entire directories, individual files, or even individual hunks within a file.

```bash
# Stage a single file
git add README.md

# Stage all changes in the current directory and subdirectories
git add .

# Stage all tracked and untracked changes across the entire repository
git add --all

# Interactively choose which hunks of a file to stage
git add -p src/app.js
```

The `-p` (patch) flag is powerful: it walks you through each changed section of a file and asks whether to stage it. This lets you craft a focused commit even when your working directory contains multiple unrelated edits.

A critical point: if you modify a file after staging it, the staged version remains unchanged. You must run `git add` again to capture the newer edits.

### git commit — Recording a Snapshot

`git commit` permanently stores the staged changes as a new snapshot in the repository. Every commit requires a message. Without a clear message, the history becomes useless for future readers — including yourself.

```bash
# Commit with an inline message (most common)
git commit -m "Add user authentication endpoint"

# Open your configured editor to write a multi-line message
git commit

# Stage all tracked files and commit in one step (skips untracked files)
git commit -am "Fix null pointer in payment processor"

# Modify the most recent commit (before pushing)
git commit --amend -m "Fix null pointer in payment processor — add null check"
```

A well-structured commit message follows the convention: a subject line of 50 characters or fewer in the imperative mood ("Add feature", not "Added feature"), optionally followed by a blank line and a longer body explaining the why.

### git log — Reading History

`git log` displays the commit history in reverse chronological order. The default output is verbose; you will almost always add flags to make it readable.

```bash
# Default output — full commit hash, author, date, message
git log

# Compact one-line-per-commit format
git log --oneline

# Graph view showing branch and merge topology
git log --oneline --graph --all --decorate

# Limit to the last five commits
git log -n 5

# Filter by author
git log --author="Alice"

# Filter by date range
git log --since="2 weeks ago" --until="1 week ago"

# Show commits that affected a specific file
git log -- src/app.js

# Custom format: abbreviated hash, author name, relative date, subject
git log --format="%h  %an  %ar  %s"
```

The `--graph --all --decorate` combination is especially useful: it draws your full branch topology as ASCII art and labels branch tips and tags by name.

### git diff — Inspecting Changes

`git diff` compares file content across different states of the repository. The most common confusion is forgetting which two states are being compared.

```bash
# Changes in working directory NOT yet staged (working vs. staging area)
git diff

# Changes that ARE staged, compared to the last commit
git diff --staged
git diff --cached   # identical to --staged

# All changes (staged + unstaged) compared to the last commit
git diff HEAD

# Compare two branches
git diff main feature/login

# Compare the current working tree to a specific commit
git diff abc1234 -- src/app.js

# Summary of which files changed and how many lines
git diff --stat

# Word-level diff instead of line-level
git diff --word-diff
```

Output uses `+` (green) for added lines and `-` (red) for removed lines. Lines without a prefix are unchanged context lines.

### git branch and git checkout — Working with Branches

A branch in Git is simply a lightweight pointer to a commit. Creating a branch is nearly instant because Git only writes a 41-byte file. Branches are how you isolate work, experiment safely, and collaborate in parallel.

```bash
# List all local branches (* marks the current branch)
git branch

# List all branches including remote-tracking branches
git branch -a

# Create a new branch (does NOT switch to it)
git branch feature/user-profile

# Switch to an existing branch
git checkout feature/user-profile

# Create a new branch AND switch to it in one step
git checkout -b feature/shopping-cart

# Delete a branch (only if its changes are already merged)
git branch -d feature/old-work

# Force-delete a branch regardless of merge status
git branch -D feature/abandoned-work
```

From Git 2.23 onward, `git switch` and `git restore` were introduced as purpose-specific alternatives to the overloaded `git checkout`. Both are now stable; this module covers `git checkout` because you will encounter it in older scripts and documentation. Module 2 covers `git switch` and `git restore`.

```bash
# Modern equivalent: switch to a branch
git switch feature/user-profile

# Modern equivalent: create and switch to a new branch
git switch -c feature/shopping-cart
```

### git merge — Integrating Work

`git merge` incorporates changes from one branch into the current branch. The most common pattern is merging a feature branch back into `main` after review.

```bash
# First, switch to the target branch
git checkout main

# Merge a feature branch into main
git merge feature/user-profile

# Merge with an explicit merge commit (no fast-forward)
git merge --no-ff feature/user-profile

# Abort a merge that has produced conflicts
git merge --abort
```

Git automatically performs a **fast-forward merge** when the target branch has no commits that diverge from the source — it simply moves the branch pointer forward. When the histories have diverged, Git performs a **three-way merge** and creates a new merge commit.

A **merge conflict** occurs when both branches have changed the same lines of the same file. Git marks the conflict in the file like this:

```
<<<<<<< HEAD
return user.name;
=======
return user.fullName;
>>>>>>> feature/user-profile
```

You must manually edit the file to resolve the conflict, then stage the resolved file and commit it:

```bash
# After manually editing the conflicted file
git add src/user.js
git commit -m "Merge feature/user-profile: resolve name field conflict"
```

### git remote, git push, and git pull — Collaborating via Remotes

A **remote** is a named reference to a Git repository hosted elsewhere — on GitHub, GitLab, a company server, or another machine. The name `origin` is the conventional default remote created by `git clone`.

```bash
# List all configured remotes with their URLs
git remote -v

# Add a new remote
git remote add origin https://github.com/yourname/repo.git

# Change a remote's URL
git remote set-url origin https://github.com/yourname/new-repo.git

# Remove a remote
git remote remove upstream
```

`git push` uploads local commits to a remote repository.

```bash
# Push the current branch to origin (first push requires -u to set tracking)
git push -u origin main

# Subsequent pushes on a tracked branch
git push

# Push a specific branch
git push origin feature/login
```

`git pull` fetches commits from the remote and merges them into your current branch. It is equivalent to running `git fetch` followed by `git merge`.

```bash
# Pull from the tracked remote branch
git pull

# Pull from a specific remote and branch
git pull origin main

# Pull using rebase instead of merge (keeps history linear)
git pull --rebase origin main
```

## Best Practices

1. **Commit early and commit often, but keep each commit focused on one logical change.** Small, focused commits make code review easier and allow precise rollbacks without undoing unrelated work.

2. **Write commit messages in the imperative mood and keep the subject under 50 characters.** "Add password reset endpoint" is clearer than "Added stuff for passwords" and displays cleanly in `git log --oneline`.

3. **Never commit directly to `main` or `master` for shared projects; always work on a feature branch.** Committing directly to the default branch makes it harder to review changes and increases the risk of breaking the stable codebase.

4. **Run `git status` before every `git add` and before every `git commit`.** This two-second habit prevents accidentally staging unintended files and ensures you commit only what you believe is in the staging area.

5. **Use `git add -p` instead of `git add .` when your working directory contains multiple unrelated changes.** Interactive staging lets you create clean, logical commits even when your disk is messy.

6. **Create a `.gitignore` file before the first commit.** Build artifacts, dependency directories like `node_modules/`, secrets, and editor configuration files must be excluded from day one — retroactively removing them from history is painful.

7. **Pull before you push to avoid rejected pushes.** Fetching remote changes first and merging or rebasing locally means you resolve any conflicts in a controlled environment before pushing.

8. **Use `git merge --no-ff` for feature branches in shared repositories.** A merge commit explicitly records that a group of commits was developed together as a feature, preserving that context in the log even after the branch is deleted.

9. **Never use `git push --force` on a shared branch without team consensus.** Force-pushing rewrites public history and can silently discard other people's commits; prefer `git push --force-with-lease` if a force push is truly necessary.

10. **Set your `user.name` and `user.email` in global Git config before your first commit.** These values are permanently baked into every commit you create; anonymous or incorrect attribution makes history harder to reason about.

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## Use Cases

### Use Case 1: Starting a New Solo Project

A developer begins a new web application and wants to track all changes from the first line of code.

- **Problem:** There is no version history, making it impossible to undo mistakes or understand what changed between sessions.
- **Concepts applied:** `git init`, `.gitignore`, `git add`, `git commit`
- **Expected outcome:** A local repository with an initial commit containing project scaffolding, a `.gitignore` that excludes `node_modules/` and `.env`, and a clean `git status` showing nothing to commit.

### Use Case 2: Contributing to an Existing Open-Source Project

A developer wants to fix a bug in a public repository they do not own.

- **Problem:** They need a full local copy of the codebase to work on, with the ability to push changes back for review.
- **Concepts applied:** `git clone`, `git branch`, `git checkout -b`, `git commit`, `git push`, `git remote`
- **Expected outcome:** A local clone with a feature branch containing the bug fix, pushed to their personal fork, ready to open a pull request.

### Use Case 3: Reviewing What Changed Before a Release

A team lead wants to audit all changes made to the codebase in the past two weeks before tagging a release.

- **Problem:** Without a structured history view, it is unclear what features were added and what bugs were fixed.
- **Concepts applied:** `git log --since`, `git log --author`, `git diff main..release-candidate`, `git diff --stat`
- **Expected outcome:** A concise list of commits grouped by author, a statistical summary of changed files, and confidence that the release contains only intended changes.

### Use Case 4: Syncing Work Across Multiple Machines

A developer works on the same project from both a work laptop and a home desktop.

- **Problem:** Changes made on one machine are not available on the other without a manual file transfer.
- **Concepts applied:** `git remote`, `git push`, `git pull`
- **Expected outcome:** The developer pushes completed work from the office laptop and pulls it onto the home desktop with a single command, with full history preserved on both machines.

### Use Case 5: Isolating an Experimental Feature

A developer wants to try a risky refactor without risking the stable codebase.

- **Problem:** Experimenting directly on `main` could break working software if the approach turns out to be wrong.
- **Concepts applied:** `git checkout -b`, `git commit`, `git merge`, `git branch -d`
- **Expected outcome:** The experiment lives on its own branch. If it succeeds, it is merged into `main`. If it fails, the branch is deleted and `main` is untouched.

## Hands-on Examples

### Example 1: Initialize a Repository and Make Your First Commit

You are starting a new project called `task-tracker` from scratch. This example walks through the complete setup: from an empty directory to a committed initial state.

1. Create the project directory and initialize the repository.

```bash
mkdir task-tracker
cd task-tracker
git init -b main
```

Expected output:
```
Initialized empty Git repository in /home/user/task-tracker/.git/
```

2. Configure your identity if you have not already done so globally.

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
```

3. Create a `.gitignore` and a `README.md`.

```bash
echo "node_modules/" > .gitignore
echo "# Task Tracker" > README.md
```

4. Check the status to confirm Git sees the new files.

```bash
git status
```

Expected output:
```
On branch main

No commits yet

Untracked files:
  (use "git add <file>..." to include in what will be committed)
        .gitignore
        README.md

nothing added to commit but untracked files present (use "git add" to track)
```

5. Stage both files and commit.

```bash
git add .gitignore README.md
git commit -m "Initial commit: add README and gitignore"
```

Expected output:
```
[main (root-commit) a3f9c12] Initial commit: add README and gitignore
 2 files changed, 2 insertions(+)
 create mode 100644 .gitignore
 create mode 100644 README.md
```

6. Verify the commit appears in the log.

```bash
git log --oneline
```

Expected output:
```
a3f9c12 (HEAD -> main) Initial commit: add README and gitignore
```

---

### Example 2: Feature Branch Workflow — Add, Commit, Merge

You are adding a new feature to the `task-tracker` project. You will create an isolated branch, make commits, and merge back into `main`.

1. Create and switch to a feature branch.

```bash
git checkout -b feature/add-tasks
```

Expected output:
```
Switched to a new branch 'feature/add-tasks'
```

2. Create a new source file simulating a feature.

```bash
echo 'function addTask(name) { return { id: Date.now(), name }; }' > tasks.js
```

3. Stage and commit the new file.

```bash
git add tasks.js
git commit -m "Add addTask function to tasks module"
```

Expected output:
```
[feature/add-tasks 7b2e4a1] Add addTask function to tasks module
 1 file changed, 1 insertion(+)
 create mode 100644 tasks.js
```

4. Make a second commit to simulate continued work.

```bash
echo 'function listTasks(tasks) { return tasks.map(t => t.name); }' >> tasks.js
git add tasks.js
git commit -m "Add listTasks function to tasks module"
```

5. View the branch history.

```bash
git log --oneline --graph --all --decorate
```

Expected output:
```
* 3c1a8f0 (HEAD -> feature/add-tasks) Add listTasks function to tasks module
* 7b2e4a1 Add addTask function to tasks module
* a3f9c12 (main) Initial commit: add README and gitignore
```

6. Switch back to `main` and merge the feature branch using `--no-ff` to preserve branch context.

```bash
git checkout main
git merge --no-ff feature/add-tasks -m "Merge feature/add-tasks: task CRUD functions"
```

Expected output:
```
Merge made by the 'ort' strategy.
 tasks.js | 2 ++
 1 file changed, 2 insertions(+)
 create mode 100644 tasks.js
```

7. Clean up the merged branch.

```bash
git branch -d feature/add-tasks
```

Expected output:
```
Deleted branch feature/add-tasks (was 3c1a8f0).
```

---

### Example 3: Connecting to a Remote and Pushing

You have the local `task-tracker` repository and want to push it to a remote host. This example assumes you have already created an empty repository on GitHub (or any Git host) and have its URL.

1. Add the remote.

```bash
git remote add origin https://github.com/yourname/task-tracker.git
```

2. Verify the remote was added correctly.

```bash
git remote -v
```

Expected output:
```
origin  https://github.com/yourname/task-tracker.git (fetch)
origin  https://github.com/yourname/task-tracker.git (push)
```

3. Push the `main` branch and set it as the upstream tracking branch.

```bash
git push -u origin main
```

Expected output:
```
Enumerating objects: 7, done.
Counting objects: 100% (7/7), done.
Delta compression using up to 8 threads
Compressing objects: 100% (4/4), done.
Writing objects: 100% (7/7), 612 bytes | 612.00 KiB/s, done.
Total 7 (delta 0), reused 0 (delta 0), pack-reused 0
To https://github.com/yourname/task-tracker.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
```

4. Simulate a remote change (edit a file in the GitHub UI or on another machine) then pull it down.

```bash
git pull
```

Expected output when remote has a new commit:
```
remote: Enumerating objects: 5, done.
Updating a3f9c12..d9f1234
Fast-forward
 README.md | 2 ++
 1 file changed, 2 insertions(+)
```

---

### Example 4: Using git diff to Understand Changes

You have edited files and want to understand exactly what is staged versus what is not before committing.

1. Edit an existing file.

```bash
echo 'function deleteTask(tasks, id) { return tasks.filter(t => t.id !== id); }' >> tasks.js
```

2. Stage only part of the file using interactive staging.

```bash
git add -p tasks.js
```

Git will display each changed hunk and prompt `Stage this hunk [y,n,q,a,d,s,?]?`. Enter `y` to stage the hunk.

3. Check what is staged versus what remains unstaged.

```bash
# Staged changes (what will go into the next commit)
git diff --staged
```

Expected output shows the staged hunk with a `+` prefix.

4. Make another edit to the same file without staging it.

```bash
echo '// TODO: add updateTask function' >> tasks.js
```

5. View unstaged changes.

```bash
git diff
```

Expected output shows only the TODO comment line, not the already-staged deleteTask function.

6. Commit only the staged portion.

```bash
git commit -m "Add deleteTask function to tasks module"
```

The TODO comment remains in the working directory, unstaged, for a future commit.

## Common Pitfalls

### Pitfall 1: Staging Everything with `git add .` and Accidentally Committing Unwanted Files

**Description:** Running `git add .` stages every changed and new file in the current directory tree, including temporary files, secrets, build outputs, and editor configuration that you never intended to commit.

**Why it happens:** `git add .` is the shortest command to stage changes and beginners reach for it reflexively, not realizing it captures everything that is not explicitly excluded by `.gitignore`.

**Incorrect pattern:**
```bash
# .env file containing API keys is in the working directory
git add .
git commit -m "Add feature"
# .env is now permanently in the repository history
```

**Correct pattern:**
```bash
# Create .gitignore first
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Ignore .env file"

# Then use git status to inspect before staging
git status
git add src/feature.js
git commit -m "Add feature"
```

---

### Pitfall 2: Committing Without a Meaningful Message

**Description:** Using vague messages like `"fix"`, `"wip"`, `"asdf"`, or `"updated stuff"` makes the commit history useless as documentation.

**Why it happens:** Developers are focused on the code and treat the commit message as a bureaucratic hurdle rather than a valuable communication tool.

**Incorrect pattern:**
```bash
git commit -m "fix"
```

**Correct pattern:**
```bash
git commit -m "Fix off-by-one error in pagination: last page now displays correctly"
```

---

### Pitfall 3: Forgetting to Stage Changes After Editing a Previously Staged File

**Description:** A developer stages a file, then makes additional edits to it, and commits — expecting all edits to be included. Only the version that existed at the time of `git add` is committed.

**Why it happens:** It is unintuitive that the staging area holds a snapshot of the file at the moment `git add` was run, not a live reference to the file on disk.

**Incorrect pattern:**
```bash
git add app.js         # Stages current version
# ... edit app.js again ...
git commit -m "Update app"   # Commits the PRE-edit version
```

**Correct pattern:**
```bash
git add app.js         # Stages current version
# ... edit app.js again ...
git add app.js         # Re-stage to capture the newer edits
git commit -m "Update app"   # Now commits the latest version
```

---

### Pitfall 4: Pulling After Making Local Commits Without a Strategy

**Description:** Running a plain `git pull` when both local and remote branches have diverged creates an unnecessary merge commit in the history, cluttering it with "Merge branch 'main' of ..." entries.

**Why it happens:** `git pull` defaults to a merge strategy. When the remote has new commits and so does the local branch, a three-way merge commit is created automatically.

**Incorrect pattern:**
```bash
git commit -m "My local work"
git pull   # Creates a messy merge commit if remote also has new commits
git push
```

**Correct pattern:**
```bash
git commit -m "My local work"
git pull --rebase origin main  # Replays your commits on top of the remote changes
git push
```

---

### Pitfall 5: Deleting a Branch Before Merging Its Changes

**Description:** A developer deletes a feature branch using `git branch -D` before its commits have been merged anywhere, permanently losing that work.

**Why it happens:** The `-D` (capital D) flag is a force-delete that bypasses the safety check Git normally performs. Developers sometimes reach for it when `-d` gives a warning about unmerged commits.

**Incorrect pattern:**
```bash
git branch -D feature/experiment   # Commits are gone if not merged or pushed
```

**Correct pattern:**
```bash
# Use lowercase -d, which refuses to delete if commits are unmerged
git branch -d feature/experiment
# If Git warns: "error: The branch 'feature/experiment' is not fully merged"
# Either merge first, or explicitly push the branch to preserve it remotely
git push origin feature/experiment
git branch -D feature/experiment   # Now safe to force-delete locally
```

---

### Pitfall 6: Using `git commit -am` to Stage Untracked Files

**Description:** A developer adds a brand-new file, then runs `git commit -am "..."` expecting it to be included in the commit. The new file is silently omitted.

**Why it happens:** The `-a` flag in `git commit -am` only stages changes to files that Git is already **tracking**. Untracked (new) files are not tracked until their first `git add`.

**Incorrect pattern:**
```bash
touch newfile.js          # New, untracked file
git commit -am "Add newfile"  # newfile.js is NOT included
```

**Correct pattern:**
```bash
touch newfile.js
git add newfile.js         # Must explicitly add new files
git commit -m "Add newfile"
```

---

### Pitfall 7: Confusing `git diff` and `git diff --staged`

**Description:** A developer runs `git diff` and sees no output, incorrectly concluding there are no changes. In reality, changes have been staged and `git diff` only shows unstaged differences.

**Why it happens:** The default `git diff` compares the working directory against the staging area, not against the last commit. If all changes are staged, it produces no output.

**Incorrect pattern:**
```bash
git add app.js
git diff        # Shows nothing; developer thinks no changes exist
```

**Correct pattern:**
```bash
git add app.js
git diff --staged   # Shows the staged changes correctly
git diff HEAD       # Shows all changes (staged + unstaged) vs last commit
```

## Summary

- Git tracks your project across three areas — the working directory, the staging area, and the repository — and every core command operates on the movement of changes between these areas.
- The `git add` / `git commit` two-step workflow gives you explicit control over exactly what goes into each snapshot, enabling focused and meaningful commit history.
- Branches are cheap and fast; creating a new branch with `git checkout -b` before any non-trivial change is a habit that protects the stable codebase and enables parallel work.
- `git log`, `git status`, and `git diff` are read-only inspection tools that cost nothing to run; consulting them frequently is the single most effective habit for avoiding mistakes.
- Remotes connect your local repository to hosted copies; `git push` and `git pull` synchronize work and are the foundation of every collaborative Git workflow.

## Further Reading

- [Git Official Documentation — git-scm.com](https://git-scm.com/docs) — The authoritative reference for every Git command and flag; use it to verify exact syntax and available options for any command covered in this module.
- [Pro Git Book (free online)](https://git-scm.com/book/en/v2) — A comprehensive open-source book written by Git core contributors that covers everything from basic commands through internals; Chapters 1–3 directly complement this module.
- [GitLab Common Git Commands Reference](https://docs.gitlab.com/topics/git/commands/) — A concise, production-oriented command reference maintained by GitLab; particularly useful for the `git remote`, `git push`, and `git pull` sections.
- [Atlassian Git Tutorials — Getting Started](https://www.atlassian.com/git/tutorials/setting-up-a-repository) — Vendor-neutral, diagram-rich tutorials covering every concept in this module with visual explanations of the three-tree architecture and branching model.
- [GitHub Git Cheat Sheet (PDF)](https://education.github.com/git-cheat-sheet-education.pdf) — A one-page command reference from GitHub Education covering all commands in this module; suitable for printing and keeping at your desk while learning.
- [7 Git Mistakes Developers Should Avoid — Tower Blog](https://www.git-tower.com/blog/7-git-mistakes-a-developer-should-avoid) — A practitioner-written breakdown of common workflow mistakes with concrete before/after examples; directly reinforces the Common Pitfalls section of this module.
- [Git 2.53 Release Notes — 9to5Linux](https://9to5linux.com/git-2-53-released-with-new-features-and-performance-improvements) — Covers what changed in the current stable release (2.53.0, released 2026-02-02), useful for understanding which behaviors may differ from older installations.
