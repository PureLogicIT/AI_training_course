# Module 2: Branching and Merging Policies
> Subject: GIT | Difficulty: Intermediate | Estimated Time: 150 minutes

## Objective

After completing this module, you will be able to apply structured branching strategies to real-world team workflows, create and switch branches using the modern `git switch` command, explain the differences between fast-forward, squash, and rebase merge strategies and choose the right one for a given situation, resolve merge conflicts methodically, use `git stash` to safely context-switch between tasks, configure branch protection rules on a hosted repository, and articulate why Trunk-Based Development has become the dominant model in continuous-delivery teams.

## Prerequisites

- Completion of Module 1: Basic Commands — you must be comfortable with `git init`, `git add`, `git commit`, `git log`, `git branch`, `git checkout`, `git merge`, `git push`, and `git pull`
- Git 2.40 or later installed (`git --version`; current stable release is 2.53.0)
- A free GitHub or GitLab account for the branch protection rules section
- Basic understanding of what a merge conflict marker looks like (introduced briefly in Module 1)

## Key Concepts

### Branching Strategies

A **branching strategy** is a team agreement about which branches exist at any time, how long they live, and how code flows between them. Choosing the wrong strategy for your team size or release cadence creates unnecessary merge complexity; choosing the right one is nearly invisible because it feels natural.

#### Git Flow

Git Flow, introduced by Vincent Driessen in 2010, uses five named branch types with strict rules about how they interact.

| Branch type | Purpose | Lifetime |
|------------|---------|---------|
| `main` | Production-ready code only | Permanent |
| `develop` | Integration branch for completed features | Permanent |
| `feature/*` | Individual features in progress | Temporary |
| `release/*` | Stabilization before a versioned release | Temporary |
| `hotfix/*` | Emergency production fixes | Temporary |

The flow for a new feature: branch `feature/my-feature` off `develop` → commit work → open a pull request back into `develop` → delete the feature branch. When enough features accumulate, a `release/1.2.0` branch is cut from `develop`, hardened, then merged into both `main` (tagged with the version) and back into `develop`.

Git Flow works well for software that ships versioned releases on a schedule (desktop apps, mobile apps, libraries with semantic versioning). It struggles for teams doing continuous deployment because the branching overhead slows down delivery.

```
main       ----*-----------*-----------> (tagged releases)
               |           ^
develop   -----.---.---.---.------>
               \  /   \  /
feature/*   ---*-*     *-*
```

#### GitHub Flow

GitHub Flow reduces Git Flow to its essence. There are only two rules: `main` is always deployable, and all changes happen on short-lived feature branches that are immediately merged via pull request after review.

```
main       ---*-----*-----*-----*----->
               \   / \   / \   /
feature/*   ---*---   *---   *---
```

GitHub Flow is the right choice for small teams, web services that can redeploy at any time, and any project that does not need to maintain multiple production versions simultaneously.

#### Trunk-Based Development (TBD)

Trunk-Based Development takes GitHub Flow even further by shrinking branch lifetime to hours, not days. All developers integrate to a single trunk (typically `main`) at least once every 24 hours. For features that are not ready to be exposed to users, **feature flags** (runtime configuration switches) hide incomplete work rather than keeping it on a branch.

TBD requires strong discipline: every commit to trunk must not break the build, tests must run in a CI pipeline on every push, and developers must decompose work into small, safe increments. In exchange, merge conflicts become rare and shallow, and deployment frequency becomes a team superpower.

The 2024 DORA (DevOps Research and Assessment) report consistently finds that teams practicing TBD score significantly higher on all four key DevOps metrics: deployment frequency, lead time for changes, change failure rate, and mean time to recover.

**How to choose:**

| Team size | Release cadence | Recommended strategy |
|-----------|----------------|---------------------|
| 1–5 developers | Continuous deployment | GitHub Flow or TBD |
| 5–20 developers | Continuous deployment | TBD with feature flags |
| Any size | Scheduled versioned releases | Git Flow |
| Enterprise, compliance-heavy | Controlled releases | Git Flow or GitLab Flow |

---

### git switch and git restore — The Modern Alternatives

Module 1 used `git checkout` for branch operations because it is ubiquitous in legacy scripts and documentation. From Git 2.23 onward, `git checkout`'s two roles — switching branches and restoring files — were split into dedicated commands. Both are stable and are now the preferred approach in interactive use.

**`git switch`** handles branch operations:

```bash
# Switch to an existing branch
git switch develop

# Create a new branch and switch to it
git switch -c feature/user-auth

# Create a branch from a specific starting point
git switch -c hotfix/login-crash main

# Return to the previous branch (equivalent to git checkout -)
git switch -

# Switch to a specific commit in detached HEAD state
git switch --detach abc1234
```

**`git restore`** handles file restoration:

```bash
# Discard working directory changes to a file (restore from the index)
git restore src/app.js

# Unstage a file (restore the index from HEAD)
git restore --staged src/app.js

# Restore a file from a specific commit
git restore --source=HEAD~2 src/app.js
```

The separation of concerns is the key advantage: `git switch` will never accidentally overwrite a file, and `git restore` will never accidentally move you to a different branch. You can still use `git checkout` — it is not deprecated — but prefer `git switch` and `git restore` in any new scripts or workflows.

---

### Creating, Switching, and Deleting Branches

```bash
# List all local branches; * marks the currently active branch
git branch

# List all branches including remote-tracking branches
git branch -a

# List branches showing the most recent commit on each
git branch -v

# Create a branch without switching to it
git branch feature/search

# Create and switch in one command (preferred)
git switch -c feature/search

# Rename a branch you are currently on
git branch -m feature/serach feature/search

# Rename a branch you are NOT on
git branch -m old-name new-name

# Delete a branch — safe: refuses if commits are unmerged
git branch -d feature/search

# Force-delete — use only after confirming commits are merged or pushed
git branch -D feature/abandoned-spike

# Delete a remote branch
git push origin --delete feature/old-branch

# List branches that have been merged into main (safe to delete)
git branch --merged main

# List branches that have NOT been merged into main
git branch --no-merged main
```

---

### Merge Strategies

When you run `git merge`, Git selects a strategy based on how the branches have diverged. Understanding each strategy helps you choose intentionally rather than accepting Git's default.

#### Fast-Forward Merge

A fast-forward occurs when the target branch has not added any new commits since the source branch was created. Git simply moves the branch pointer forward along the existing commit chain — no new commit is created.

```
Before:  main ---A---B
                      \
         feature       C---D

After:   main ---A---B---C---D   (HEAD moved forward; no merge commit)
```

```bash
# Fast-forward happens automatically when possible
git switch main
git merge feature/quick-fix

# Force a merge commit even when fast-forward is possible
git merge --no-ff feature/quick-fix

# Refuse to merge if it would require a non-fast-forward merge commit
git merge --ff-only feature/quick-fix
```

Use `--no-ff` on feature branches in shared repositories. Merge commits preserve the fact that a group of commits belongs to a logical unit of work, even after the branch is deleted.

Use `--ff-only` in automation scripts when you want to guarantee a clean history and fail loudly if the branch is not up to date.

#### Three-Way Merge (ORT Strategy)

When both branches have diverged — each has commits the other does not — Git performs a three-way merge using the two branch tips and their common ancestor. Git 2.33 introduced the **ORT** (Ostensibly Recursive's Twin) strategy, which became the default in Git 2.34. In Git 2.50.0, `recursive` became a synonym for `ort`. ORT is faster, handles renames correctly, and produces fewer spurious conflicts than the old recursive strategy.

```
Before:  main ---A---B---E
                      \
         feature       C---D

After:   main ---A---B---E---M   (M is the new merge commit)
                      \   /
         feature       C---D
```

The three-way merge requires manual conflict resolution only when both branches have modified the same lines in the same file.

#### Squash Merge

A squash merge collapses all commits from the feature branch into a single combined change set, stages it, and then requires you to create one new commit manually. The feature branch's individual commits are not recorded in the target branch's history.

```
Before:  main ---A---B
                      \
         feature       C---D---E

After merge --squash + commit:
         main ---A---B---S   (S contains all changes from C, D, E in one commit)
         feature       C---D---E  (unchanged; branch still exists)
```

```bash
git switch main
git merge --squash feature/new-dashboard
# Staging area is now populated with all changes from the feature branch
git commit -m "Add new dashboard: charts, filters, and export button"
```

Squash merges are ideal when a feature branch has many messy "wip" or "fix typo" commits that you do not want polluting `main`'s history. The trade-off is that `main` loses traceability to the original author of individual changes — a concern for large teams.

#### Rebase and Merge (Linear History)

Rebasing replays the commits from a feature branch on top of the tip of the target branch, rewriting their parent pointers. The result looks as if the feature branch was created from the latest commit on `main` — a perfectly linear history.

```
Before:  main ---A---B---E
                      \
         feature       C---D

After rebase:
         main ---A---B---E
                          \
         feature (rebased) C'---D'  (new commits, same changes)

After merge --ff-only:
         main ---A---B---E---C'---D'
```

```bash
# Rebase the feature branch onto main
git switch feature/new-dashboard
git rebase main

# If conflicts arise during rebase, resolve them, then:
git add src/dashboard.js
git rebase --continue

# To abort and return to the pre-rebase state
git rebase --abort

# Now fast-forward merge — no merge commit needed
git switch main
git merge --ff-only feature/new-dashboard
```

**The golden rule of rebasing: never rebase commits that have been pushed to a shared remote branch.** Rebasing rewrites commit hashes. If teammates have built work on those original hashes, their history will conflict with your rewritten version, forcing them to run `git pull --rebase` or causing serious divergence.

---

### Merge Conflicts: How They Happen and How to Resolve Them

A conflict arises when two branches have each modified the same region of the same file in different ways, and Git cannot determine which version to keep. Git pauses the merge and marks the conflicting sections in the file.

**Anatomy of a conflict marker:**

```
<<<<<<< HEAD
const timeout = 3000;
=======
const timeout = 5000;
>>>>>>> feature/increase-timeout
```

- Everything between `<<<<<<< HEAD` and `=======` is the version from your current branch.
- Everything between `=======` and `>>>>>>> branch-name` is the incoming version.
- You must delete all three marker lines and leave only the code you want.

**The full resolution workflow:**

```bash
# 1. Attempt the merge
git switch main
git merge feature/increase-timeout
# Output: CONFLICT (content): Merge conflict in src/config.js
# Automatic merge failed; fix conflicts and then commit the result.

# 2. Identify all conflicted files
git status
# Both modified: src/config.js

# 3. Open each conflicted file, resolve the markers, save
# (use your editor; the file now contains only the correct code)

# 4. Stage the resolved file — this signals to Git that the conflict is resolved
git add src/config.js

# 5. Verify nothing else is conflicted
git status

# 6. Complete the merge with a meaningful message
git commit -m "Merge feature/increase-timeout: use 5000ms timeout for slow networks"
```

**Aborting a merge you are not ready to resolve:**

```bash
git merge --abort
# Restores the repository to the state before the merge was attempted
```

**Useful tools for conflict resolution:**

```bash
# Launch a configured visual merge tool (e.g., VS Code, vimdiff, IntelliJ)
git mergetool

# Show the common ancestor version of a conflicted file
git show :1:src/config.js   # ancestor
git show :2:src/config.js   # current branch (HEAD)
git show :3:src/config.js   # incoming branch

# Accept all changes from the current branch for one file
git checkout --ours src/config.js

# Accept all changes from the incoming branch for one file
git checkout --theirs src/config.js
# Remember to git add after using --ours or --theirs
```

Configure VS Code as the default merge tool:

```bash
git config --global merge.tool vscode
git config --global mergetool.vscode.cmd 'code --wait $MERGED'
```

---

### git stash — Safe Context Switching

`git stash` temporarily shelves your uncommitted changes so you can switch tasks without creating a premature commit. Think of it as a clipboard for your working directory.

**Basic workflow:**

```bash
# Stash all tracked changes (working directory + staged changes)
git stash push -m "WIP: refactor payment validation"

# List all stashes
git stash list
# stash@{0}: On feature/payments: WIP: refactor payment validation
# stash@{1}: On main: WIP: update README

# Apply the most recent stash and remove it from the stash list
git stash pop

# Apply without removing (useful if you want to apply to multiple branches)
git stash apply stash@{0}

# Show what is in a stash
git stash show -p stash@{0}

# Drop a specific stash entry
git stash drop stash@{1}

# Delete all stash entries
git stash clear
```

**Stashing untracked files:**

By default, `git stash push` only saves changes to files Git is already tracking. New, untracked files are left in the working directory.

```bash
# Include untracked files in the stash
git stash push -u -m "WIP: add new config file"

# Include both untracked and ignored files
git stash push -a -m "Full working directory backup"
```

**Stashing only staged changes:**

```bash
# Stash only what is in the staging area; leave working directory edits intact
git stash push -S -m "WIP: staged part of feature"
```

**Practical context-switch workflow:**

```bash
# Scenario: You are halfway through a feature when an urgent bug is reported

# 1. Stash your in-progress work
git stash push -m "WIP: user profile page redesign"

# 2. Switch to main and create a hotfix branch
git switch main
git switch -c hotfix/broken-login

# 3. Fix, commit, and push the hotfix
git commit -am "Fix broken login redirect for SSO users"
git push origin hotfix/broken-login

# 4. Return to your feature branch
git switch feature/profile-redesign

# 5. Re-apply your stashed work
git stash pop
```

**Important note on the deprecated `git stash save` syntax:** The `git stash save` command is deprecated in favor of `git stash push`. Both work in current Git versions, but all new scripts should use `push`.

---

### Pull Request / Merge Request Policies

A **pull request (PR)** on GitHub or a **merge request (MR)** on GitLab is a proposal to merge a source branch into a target branch. Beyond the code review conversation, PRs enforce team policies before changes reach protected branches.

**Effective PR policies typically include:**

- **Minimum approval count:** Require at least one or two approving reviews from teammates before merging is allowed. This enforces a second pair of eyes on every change.
- **Required CI checks:** The PR cannot be merged until automated test suites, linters, and security scanners pass. This is the primary mechanism for keeping `main` green.
- **Stale review dismissal:** If new commits are pushed after an approval, the approval is automatically dismissed. Reviewers must re-approve against the latest code.
- **Code owner approval:** Designated owners of specific directories or files (defined in a `CODEOWNERS` file) must approve PRs that touch their areas.
- **Up-to-date branch requirement:** The source branch must be current with the target branch before merging. This ensures CI ran against the actual code that will land on `main`, not a stale combination.
- **Resolved conversation requirement:** All review comments must be explicitly resolved before merging, preventing changes from being silently ignored.

**The `CODEOWNERS` file** lives in the repository root or `.github/` and maps file patterns to required reviewers:

```
# Format: <pattern>  <owner> [<owner2> ...]

# All JavaScript files require review from the frontend team
*.js    @org/frontend-team

# Database migrations require the DBA
/db/migrations/    @alice @bob

# The entire API directory requires the backend team lead
/src/api/    @carol
```

---

### Branch Protection Rules

Branch protection rules prevent direct pushes to critical branches and enforce the PR policies described above. They are configured per-branch (or per-pattern) in the repository settings of your hosting provider.

**GitHub branch protection settings (Settings → Branches → Add rule):**

| Rule | What it enforces |
|------|----------------|
| Require a pull request before merging | No direct pushes; all changes must arrive via PR |
| Required approvals (1–6) | Minimum number of approving reviews |
| Dismiss stale reviews | Auto-dismiss approvals when new commits are pushed |
| Require review from Code Owners | Owners defined in `CODEOWNERS` must approve |
| Require status checks to pass | Named CI jobs must be green before merging |
| Require branches to be up to date | Source branch must be current with the target |
| Require conversation resolution | All PR comments must be resolved |
| Require signed commits | Only GPG-verified commits are accepted |
| Require linear history | Disallow merge commits; squash or rebase required |
| Restrict who can push | Only specified teams or users can push to the branch |
| Allow force pushes | Selectively grant force-push access |
| Allow deletions | Control whether the branch can be deleted |

**Rulesets (GitHub's newer approach):** GitHub introduced Repository Rulesets as a more flexible and inheritable alternative to branch protection rules. Rulesets support the same settings but can be applied by pattern (e.g., all branches matching `release/**`) and can be inherited across an organization.

**Applying branch protection on `main` — a baseline configuration for any team project:**

1. Navigate to your repository → Settings → Branches.
2. Click "Add branch protection rule".
3. Set "Branch name pattern" to `main`.
4. Enable: "Require a pull request before merging", set required approvals to 1.
5. Enable: "Require status checks to pass before merging" and add your CI workflow name.
6. Enable: "Do not allow bypassing the above settings".
7. Save the rule.

After this, even the repository owner must go through a PR to change `main`.

---

### Rebase vs. Merge: Choosing Intentionally

The choice between rebase and merge is not about correctness — both produce the same code. It is about what story your history tells.

| Concern | Merge | Rebase |
|---------|-------|--------|
| History accuracy | Preserves the real timeline of events | Rewrites history to appear linear |
| Commit hashes | Original hashes are preserved | Commits are rewritten with new hashes |
| Safe for shared branches | Yes | No — never rebase a pushed shared branch |
| Merge conflicts | Resolved once, in the merge commit | Resolved once per replayed commit |
| `git bisect` usability | Harder with many merge commits | Easier with linear history |
| Blame clarity | Preserved per original commit | Preserved per rebased commit |

**When to use merge:**
- Merging a completed, reviewed feature branch into `main` — use `--no-ff` to preserve the branch context in history.
- Incorporating upstream changes into a long-running shared branch where teammates also have commits.
- Anytime you are unsure — merge is always safe.

**When to use rebase:**
- Updating a local feature branch with the latest changes from `main` before opening a pull request. This makes the PR diff cleaner and eliminates unnecessary merge commits.
- Cleaning up a personal branch before sharing it (interactive rebase — covered in Module 4).
- Teams that have agreed on a linear-history convention (also enforceable via branch protection).

**The practical pattern used by most teams:**

```bash
# Developer updates their local feature branch before opening a PR
git switch feature/search
git fetch origin
git rebase origin/main       # Rebase local work on top of latest main

# If conflicts:
# resolve conflicts, git add, git rebase --continue

git push --force-with-lease origin feature/search
# --force-with-lease is safer than --force:
# it aborts if someone else has pushed to the branch since your last fetch
```

Note: `--force-with-lease` checks that no one else has pushed to the remote branch since you last fetched. It will refuse to overwrite commits you have not seen, preventing silent data loss that plain `--force` can cause.

---

## Best Practices

1. **Pick one branching strategy and document it in your repository's README or CONTRIBUTING file.** Inconsistency across team members is more damaging than any specific strategy choice.

2. **Prefer `git switch` and `git restore` over `git checkout` for branch and file operations.** The split commands have explicit, single purposes that reduce the chance of operating on the wrong thing.

3. **Keep feature branches short-lived — under three days if possible.** Long-lived branches accumulate divergence and produce massive, hard-to-review pull requests. If a feature takes weeks, use feature flags to merge incrementally.

4. **Always use `--no-ff` when merging feature branches into `main` in a Git Flow or GitHub Flow project.** The merge commit is a historical artifact that shows the feature as a unit, which is invaluable when tracing bugs with `git log`.

5. **Name stashes with a `-m` message.** Stash entries referenced only by index (`stash@{0}`) become inscrutable after a few context switches; a message like `WIP: fix pagination offset` is self-documenting.

6. **Do not stash for more than a few hours; commit instead.** A stash is not a branch. If you need to set work aside for more than a short break, commit it to a WIP branch and push it so it is backed up and visible to teammates.

7. **Rebase your feature branch onto `main` locally before opening a pull request.** This ensures your PR's diff contains only your changes, CI runs against the actual integration result, and reviewers see a clean, linear set of commits.

8. **Never force-push to `main` or any other shared protected branch.** If you must amend or rewrite history on a personal branch that has been pushed, use `--force-with-lease` instead of `--force`.

9. **Enable branch protection rules before your team writes the first line of code.** Retrofitting protection rules after habits have formed is harder than establishing them from the start.

10. **Resolve merge conflicts in small steps.** When a conflict file is large, use `git mergetool` to get a visual three-panel view rather than editing raw markers. Commit the resolution immediately with a message that explains what you chose and why.

---

## Use Cases

### Use Case 1: Starting a Team Project with GitHub Flow

A four-person team is building a web application and needs a branching policy that supports continuous deployment to a staging environment.

- **Problem:** Without a defined strategy, developers push directly to `main`, breaking the build for everyone.
- **Concepts applied:** GitHub Flow, `git switch -c`, pull requests, `git merge --no-ff`, branch protection rules requiring one approval and green CI.
- **Expected outcome:** Every feature ships as a PR, CI runs on every push, no one can merge without a review, and `main` is always deployable.

### Use Case 2: Urgent Hotfix in a Git Flow Project

A release manager receives a critical bug report on a production version while the team is mid-sprint on `develop`.

- **Problem:** The bugfix must reach production without pulling in incomplete sprint work sitting on `develop`.
- **Concepts applied:** Git Flow `hotfix/*` branch off `main`, `git stash` to set aside in-progress work, `git merge --no-ff` back into both `main` and `develop`, tagging the release.
- **Expected outcome:** A `hotfix/1.2.1` branch is created from `main`, the fix is applied, merged into `main` (tagged `v1.2.1`) and into `develop`, and the developer resumes their sprint work via `git stash pop`.

### Use Case 3: Cleaning Up Before Opening a Pull Request

A developer has made five commits on a feature branch but three of them are "wip" or "fix typo" commits that would clutter `main`.

- **Problem:** The pull request history is noisy, making code review harder and `git blame` less useful.
- **Concepts applied:** `git rebase origin/main` to bring the branch current, squash merge strategy to collapse noisy commits into one clean commit on `main`.
- **Expected outcome:** A single, well-described commit lands on `main` representing the entire feature, while the full development history is preserved on the feature branch until it is deleted.

### Use Case 4: Enforcing Code Ownership on a Monorepo

A team of fifteen engineers shares a monorepo with a backend API, a frontend app, and a shared library. Changes to the shared library have caused production incidents when merged without expert review.

- **Problem:** Any developer can merge changes to the shared library without the senior engineer who owns it signing off.
- **Concepts applied:** `CODEOWNERS` file mapping `/shared-lib/` to the senior engineer's GitHub username, branch protection rule requiring Code Owner approval.
- **Expected outcome:** Any PR touching files under `/shared-lib/` automatically requests review from the designated owner, and the PR cannot be merged until they approve.

---

## Hands-on Examples

### Example 1: Implement GitHub Flow from Scratch

You will set up a project, configure branch protection, and complete one full GitHub Flow cycle.

1. Continue from the `task-tracker` repository created in Module 1, or re-initialize it.

```bash
mkdir task-tracker
cd task-tracker
git init -b main
echo "# Task Tracker" > README.md
git add README.md
git commit -m "Initial commit: add README"
```

2. Push the repository to GitHub. Create an empty repository on GitHub first (do not initialize it with any files), then:

```bash
git remote add origin https://github.com/yourname/task-tracker.git
git push -u origin main
```

3. Create a feature branch using `git switch`:

```bash
git switch -c feature/add-priority-field
```

4. Make two commits on the feature branch.

```bash
echo 'const PRIORITIES = ["low", "medium", "high"];' > priority.js
git add priority.js
git commit -m "Add PRIORITIES constant to priority module"

echo 'function validatePriority(p) { return PRIORITIES.includes(p); }' >> priority.js
git add priority.js
git commit -m "Add validatePriority function to priority module"
```

5. View the branch topology.

```bash
git log --oneline --graph --all --decorate
```

Expected output:
```
* 4f8b2c1 (HEAD -> feature/add-priority-field) Add validatePriority function to priority module
* 9a3d7e0 Add PRIORITIES constant to priority module
* a1b2c3d (main, origin/main) Initial commit: add README
```

6. Push the feature branch.

```bash
git push -u origin feature/add-priority-field
```

7. Open a pull request on GitHub (via the GitHub web UI or CLI). After merging via the UI, pull the changes locally.

```bash
git switch main
git pull origin main
```

8. Delete the local feature branch now that it is merged.

```bash
git branch -d feature/add-priority-field
```

Expected output:
```
Deleted branch feature/add-priority-field (was 4f8b2c1).
```

9. Verify the clean topology.

```bash
git log --oneline --graph --all --decorate
```

Expected output shows `main` at the merged commit; the feature branch pointer is gone locally.

---

### Example 2: Create, Trigger, and Resolve a Merge Conflict

This example deliberately creates a conflict so you can practice the full resolution workflow.

1. Starting from `main` in `task-tracker`, create two branches from the same point.

```bash
git switch -c feature/use-snake-case
git switch main
git switch -c feature/use-camel-case
```

2. On `feature/use-camel-case`, add a file.

```bash
echo 'const taskPriority = "medium";' > naming.js
git add naming.js
git commit -m "Add taskPriority variable (camelCase)"
```

3. Switch to `feature/use-snake-case` and add a conflicting version of the same file.

```bash
git switch feature/use-snake-case
echo 'const task_priority = "medium";' > naming.js
git add naming.js
git commit -m "Add task_priority variable (snake_case)"
```

4. Merge `feature/use-camel-case` into `feature/use-snake-case` to trigger the conflict.

```bash
git merge feature/use-camel-case
```

Expected output:
```
Auto-merging naming.js
CONFLICT (add/add): Merge conflict in naming.js
Automatic merge failed; fix conflicts and then commit the result.
```

5. Inspect the conflict markers.

```bash
cat naming.js
```

Expected output:
```
<<<<<<< HEAD
const task_priority = "medium";
=======
const taskPriority = "medium";
>>>>>>> feature/use-camel-case
```

6. Resolve the conflict by deciding which version to keep (or writing a combined solution). Open `naming.js` in your editor and replace the entire conflict block:

```bash
# Write the resolved content directly (in practice, use your editor)
echo 'const taskPriority = "medium";' > naming.js
```

7. Stage and commit the resolution.

```bash
git add naming.js
git commit -m "Resolve naming conflict: adopt camelCase convention per team standard"
```

8. Confirm the merge completed cleanly.

```bash
git log --oneline --graph --decorate
```

Expected output shows a merge commit with two parent pointers.

9. Clean up both feature branches.

```bash
git switch main
git branch -d feature/use-snake-case
git branch -d feature/use-camel-case
```

---

### Example 3: Using git stash for an Urgent Context Switch

You are mid-feature when a critical bug is reported. This example walks through a complete stash-and-return cycle.

1. Start on your feature branch with some uncommitted work.

```bash
git switch -c feature/export-to-csv
echo 'function exportToCsv(tasks) { /* TODO */ }' > export.js
echo 'const CSV_HEADER = "id,name,priority";' >> export.js
```

2. Verify `git status` shows unstaged changes.

```bash
git status
```

Expected output:
```
On branch feature/export-to-csv
Untracked files:
  (use "git add <file>..." to include in what will be committed)
        export.js

nothing added to commit but untracked files present
```

3. Stash the work, including the untracked file.

```bash
git stash push -u -m "WIP: export CSV skeleton — not ready to commit"
```

Expected output:
```
Saved working directory and index state On feature/export-to-csv: WIP: export CSV skeleton — not ready to commit
```

4. Confirm the working directory is clean.

```bash
git status
```

Expected output:
```
On branch feature/export-to-csv
nothing to commit, working tree clean
```

5. Switch to `main`, create a hotfix branch, and apply the fix.

```bash
git switch main
git switch -c hotfix/null-task-name
echo 'function safeName(task) { return task.name ?? "Untitled"; }' > safe-name.js
git add safe-name.js
git commit -m "Fix null task name crash: provide Untitled fallback"
```

6. Merge the hotfix back to `main` and clean up.

```bash
git switch main
git merge --no-ff hotfix/null-task-name -m "Merge hotfix/null-task-name: fix null crash"
git branch -d hotfix/null-task-name
```

7. Return to the feature branch and restore the stashed work.

```bash
git switch feature/export-to-csv
git stash pop
```

Expected output:
```
On branch feature/export-to-csv
Untracked files:
  (use "git add <file>..." to include in what will be committed)
        export.js

Dropped stash@{0} [WIP: export CSV skeleton — not ready to commit]
```

8. Verify the file is back.

```bash
cat export.js
```

Expected output:
```
function exportToCsv(tasks) { /* TODO */ }
const CSV_HEADER = "id,name,priority";
```

---

### Example 4: Rebase a Feature Branch Before Opening a Pull Request

A developer's feature branch has fallen behind `main` by two commits. This example shows the rebase workflow that keeps PR diffs clean.

1. Set up the scenario: two commits on `main` that happened after the feature branch was created.

```bash
git switch main
echo "v1.1.0" > VERSION
git add VERSION
git commit -m "Bump version to 1.1.0"

echo 'const MAX_TASKS = 100;' > limits.js
git add limits.js
git commit -m "Add MAX_TASKS limit constant"
```

2. Switch to the feature branch (which is behind `main`).

```bash
git switch feature/export-to-csv
git log --oneline --graph --all --decorate
```

Expected output shows `main` ahead of `feature/export-to-csv` by two commits.

3. Rebase the feature branch onto the tip of `main`.

```bash
git rebase main
```

Expected output:
```
Successfully rebased and updated refs/heads/feature/export-to-csv.
```

4. Verify the linear history.

```bash
git log --oneline --graph --all --decorate
```

Expected output shows `feature/export-to-csv` sitting directly on top of `main`'s latest commit — no merge commit, no fork in the graph.

5. If this branch had already been pushed to a remote, update it with `--force-with-lease`.

```bash
git push --force-with-lease origin feature/export-to-csv
```

---

## Common Pitfalls

### Pitfall 1: Rebasing a Branch That Has Been Pushed to a Shared Remote

**Description:** A developer rebases a feature branch that their teammate has already based additional work on. The rebase produces new commit hashes, making the teammate's branch history diverge from the remote.

**Why it happens:** Rebasing locally feels harmless, but pushing rewritten commits replaces the shared history that others have built on.

**Incorrect pattern:**
```bash
# Branch 'feature/payments' is already pushed and a teammate has commits on it
git rebase main
git push --force origin feature/payments   # Teammate's commits are now orphaned
```

**Correct pattern:**
```bash
# Use merge if the branch is truly shared
git merge main
git push origin feature/payments

# If you must rebase a pushed personal branch, use --force-with-lease
git rebase main
git push --force-with-lease origin feature/payments
# This still rewrites history — only acceptable if you own the branch alone
```

---

### Pitfall 2: Using git stash pop When a Conflict Will Occur

**Description:** A developer stashes changes, makes additional commits, then runs `git stash pop`, triggering a conflict. The stash entry remains in the stash list but the developer does not notice and runs `git stash pop` again, applying an old stash on top of already-resolved work.

**Why it happens:** `git stash pop` removes the stash entry only on a successful, conflict-free application. When there is a conflict, the entry stays, and a second careless `pop` creates a double-application mess.

**Incorrect pattern:**
```bash
git stash pop   # Conflict occurs
# Resolve conflicts without noticing the stash is still in the list
git stash pop   # Applies the same stash again — double changes
```

**Correct pattern:**
```bash
git stash pop   # Conflict occurs
git status      # Check — the stash entry is still listed
git stash list  # Confirm: stash@{0} still appears

# Resolve the conflict
git add src/config.js
git commit -m "Resolve stash pop conflict in config"

# Now manually drop the stash entry
git stash drop stash@{0}
```

---

### Pitfall 3: Merging Without Updating the Feature Branch First

**Description:** A developer opens a PR, gets approval, and merges immediately — but their branch is 30 commits behind `main`. The CI check passed against the stale branch, not against the actual integrated state. The merge breaks `main`.

**Why it happens:** CI checks run on the feature branch as it was pushed, not against the future merged state unless the "require up-to-date branch" rule is enabled.

**Incorrect pattern:**
```bash
# Feature branch diverged 30 commits ago; CI passed on the old state
git merge feature/new-reports   # CI results are now meaningless for actual integration
```

**Correct pattern:**
```bash
# Developer updates before merging (or repository enforces this via protection rules)
git switch feature/new-reports
git rebase origin/main
git push --force-with-lease origin feature/new-reports
# CI re-runs on the updated branch; merge only after it passes
```

---

### Pitfall 4: Committing Conflict Markers Accidentally

**Description:** A developer edits a conflicted file, resolves most of it, but misses one set of conflict markers. They stage and commit, pushing `<<<<<<< HEAD` markers into the codebase.

**Why it happens:** Large files with multiple conflicts make it easy to miss a marker block, especially if you are not using a visual merge tool.

**Incorrect pattern:**
```bash
git add src/api/routes.js   # File still contains <<<<<<< HEAD markers
git commit -m "Resolve merge conflict"   # Markers committed to history
```

**Correct pattern:**
```bash
# Search for unresolved markers before staging
grep -r "<<<<<<< HEAD" .

# Or use git diff to review before staging
git diff src/api/routes.js

# Stage only after confirming no markers remain
git add src/api/routes.js
git commit -m "Resolve merge conflict in routes: use /api/v2 prefix"
```

---

### Pitfall 5: Deleting a Remote Branch Before Teammates Have Reviewed Its History

**Description:** After merging a PR, a developer immediately force-deletes the remote feature branch. A teammate who was writing a review comment loses the branch context.

**Why it happens:** Auto-delete on merge is a popular GitHub setting that removes the branch as soon as a PR is merged. While generally healthy, it can disrupt teammates mid-review.

**Correct pattern:**
```bash
# Use GitHub's "Automatically delete head branches" setting with care in teams
# Communicate before deleting branches that have open review discussions

# To restore a deleted remote branch from its last known commit hash:
git push origin <last-commit-sha>:refs/heads/feature/restored-branch
```

---

## Summary

- Three dominant branching strategies — Git Flow, GitHub Flow, and Trunk-Based Development — serve different release cadences. Most modern teams default to GitHub Flow or TBD for continuous deployment and Git Flow for versioned releases.
- `git switch` and `git restore`, available from Git 2.23 onward, replace the overloaded `git checkout` with purpose-specific commands that are harder to misuse.
- Git offers four main ways to integrate branches: fast-forward (move the pointer), three-way merge with ORT (create a merge commit), squash (collapse to one commit), and rebase (rewrite history to be linear). Each produces identical code but different histories.
- Merge conflicts are resolved by editing conflict markers out of the file, staging the resolved file with `git add`, and completing the merge with `git commit`.
- `git stash push -m` shelves uncommitted work safely for short context switches; prefer committing to a WIP branch for anything longer than a few hours.
- Pull request policies and branch protection rules — minimum approvals, required CI, Code Owners, up-to-date branch requirements — are the operational mechanisms that turn a branching strategy into an enforced workflow.
- The golden rule of rebasing: never rebase commits that have already been pushed to a shared branch. Use `--force-with-lease` (not `--force`) if you must update a pushed personal branch after a rebase.

## Further Reading

- [Atlassian Git Tutorial: Gitflow Workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) — The canonical written explanation of the Git Flow model, with diagrams illustrating each branch type and the flow between them; useful as a reference when implementing Git Flow on a new project.
- [Trunk Based Development (trunkbaseddevelopment.com)](https://trunkbaseddevelopment.com/) — The primary reference site for TBD, maintained by Paul Hammant; covers the full spectrum from small team direct-to-trunk up to large-scale TBD with short-lived feature branches and feature flags.
- [Git Official Documentation: git-merge](https://git-scm.com/docs/git-merge) — Authoritative reference for every merge flag and strategy option, including ORT strategy options, `--squash`, `--no-ff`, `--ff-only`, and merge driver configuration.
- [Git Official Documentation: git-stash](https://git-scm.com/docs/git-stash) — Complete reference for all stash subcommands and options including `push`, `pop`, `apply`, `list`, `show`, `drop`, and the `--staged` and `--include-untracked` flags.
- [GitHub Docs: About Protected Branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) — Official GitHub documentation for every available branch protection setting, including the newer Rulesets system; use this when configuring protection rules on a GitHub repository.
- [Atlassian Git Tutorial: Merging vs. Rebasing](https://www.atlassian.com/git/tutorials/merging-vs-rebasing) — A thorough conceptual comparison of the two integration strategies with diagrams, the golden rule of rebasing, and practical workflow guidance for both solo and team development.
- [Git Official Documentation: git-switch](https://git-scm.com/docs/git-switch) — Reference for the modern branch-switching command introduced in Git 2.23, covering all options including `--create`, `--detach`, `--orphan`, and `--guess`.
- [LaunchDarkly Blog: Git Branching Strategies vs. Trunk-Based Development](https://launchdarkly.com/blog/git-branching-strategies-vs-trunk-based-development/) — A practitioner-focused comparison written by a feature flag vendor that has a direct stake in TBD adoption; provides balanced coverage of when each approach is appropriate and the role of feature flags in enabling TBD at scale.
