# Exercise 1: Basic Commands
> Subject: GIT | Module: 1 — Basic Commands | Estimated Time: 2–3 hours

---

## Overview

This exercise set contains three progressively challenging exercises built around a small Python project called `devlog` — a minimal developer work-log tool. Each exercise extends the same codebase, so you carry your repository forward from one exercise to the next.

You will NOT repeat the examples from the module. Instead, you will apply those concepts to new, realistic situations that require you to think carefully about which tree (working directory, staging area, or repository) you are operating on at every step.

**Prerequisites:** Git 2.40 or later (`git --version`). No GitHub account is required for Exercises 1 and 2; Exercise 3 has an optional bonus that uses one.

---

## Exercise 1 of 3: The Staging Area Is Not Your Working Directory

**Difficulty:** Beginner | **Estimated Time:** 45–60 minutes

### Learning Objectives

By the end of this exercise you will be able to:
- Initialize a repository with a correct `.gitignore` from the very first commit
- Distinguish between tracked, staged, and unstaged changes using `git status` and `git diff`
- Prove that the staging area holds a snapshot of the file at `git add` time, not a live pointer
- Craft two focused commits from a single working-directory editing session using `git add -p`
- Read `git log --oneline` to confirm commit history matches your intent

### Scenario

You have just started building `devlog`, a command-line tool that lets developers log notes against dates. The starter project contains source files but no Git repository. Your job is to initialize the repository, make an initial commit, and then make two logically separate commits from one editing session — all without accidentally committing a local secrets file that already exists in the project folder.

### Step-by-Step Instructions

#### Part A: Initialize the Repository Safely

1. Open a terminal and navigate to the starter project directory:
   ```
   GIT/Projects/Starters/Exercise1-Basic Commands/
   ```

2. List all files in the directory, including hidden files, so you can see everything present before you touch Git:
   ```bash
   ls -la
   ```
   You should see `devlog.py`, `config.py`, `README.md`, and a file called `.env`. The `.env` file contains fake credentials. **It must never be committed.**

3. Initialize the repository. Use the `-b main` flag to set the default branch name explicitly:
   ```bash
   git init -b main
   ```

4. Before staging anything, create a `.gitignore` file that excludes `.env`, Python byte-code directories, and the virtual environment folder. Use your editor or redirect a heredoc — the file must contain at least these three lines:
   ```
   .env
   __pycache__/
   venv/
   ```

5. Run `git status`. Confirm that `.env` appears under **Untracked files** at this point (before `.gitignore` is staged), then re-run `git status` after you have saved `.gitignore` — now `.env` should have disappeared from the untracked list.

   > **Hint:** Git evaluates `.gitignore` rules against the working directory in real time, even before the file is committed. If `.env` is still showing, double-check for typos in `.gitignore`.

6. Stage only `.gitignore` and commit it as the very first commit:
   ```bash
   git add .gitignore
   git commit -m "Add .gitignore: exclude .env, __pycache__, venv"
   ```

7. Now stage the remaining files (`README.md`, `devlog.py`, `config.py`) and commit them together:
   ```bash
   git add README.md devlog.py config.py
   git commit -m "Initial commit: add devlog skeleton and README"
   ```

8. Run `git log --oneline` and confirm you see exactly two commits.

#### Part B: The Staging Snapshot Trap

This part demonstrates the most misunderstood property of the staging area: it captures a **snapshot** of the file at the moment you run `git add`, not a live reference to the file on disk.

9. Open `devlog.py` in your editor. Find the `# TODO: implement log_entry` comment and replace it with a real function body (any valid Python that prints or returns something). Save the file.

10. Stage the file:
    ```bash
    git add devlog.py
    ```

11. Without committing, open `devlog.py` again and add one more line to the function — for example, a `print("Entry saved.")` statement or a second return path. Save the file but **do not run `git add` again**.

12. Now run both diff commands and study the output carefully:
    ```bash
    git diff          # What is this comparing?
    git diff --staged # What is this comparing?
    ```
    You should see your second edit in `git diff` output (working directory vs. staging area) and your first edit in `git diff --staged` output (staging area vs. last commit). The two diffs are different because the staging area still holds the snapshot from step 10.

    > **Expected insight:** `git diff` with no arguments never touches the repository. It only shows the gap between the working directory and the staging area. If you staged all your changes, `git diff` will be empty even though `git diff --staged` is not.

13. Now re-stage the file to capture your second edit:
    ```bash
    git add devlog.py
    ```
    Run `git diff` again — it should now be empty. Run `git diff --staged` — it should now include both edits.

#### Part C: Two Commits from One Editing Session

14. Open `config.py`. Make two unrelated edits in the same file:
    - Change the `LOG_FILE` path value (line with `LOG_FILE = ...`) to a different string.
    - Add a new constant below it, for example `MAX_ENTRIES = 100`.

    Save the file without committing.

15. Use interactive staging to stage only the `LOG_FILE` change, not the `MAX_ENTRIES` addition:
    ```bash
    git add -p config.py
    ```
    Git will show you each changed hunk and ask `Stage this hunk [y,n,q,a,d,s,?]?`. Stage the `LOG_FILE` hunk (`y`) and skip the `MAX_ENTRIES` hunk (`n`).

    > **Hint:** If Git shows both changes in a single hunk, type `s` to split it into smaller hunks before deciding.

16. Verify that you have a split state — one change staged, one not:
    ```bash
    git status
    git diff          # Should show MAX_ENTRIES addition (unstaged)
    git diff --staged # Should show LOG_FILE change (staged)
    ```

17. Commit the staged change with a focused message:
    ```bash
    git commit -m "Update default log file path in config"
    ```

18. Stage and commit the remaining change:
    ```bash
    git add config.py
    git commit -m "Add MAX_ENTRIES limit constant to config"
    ```

19. Run `git log --oneline` and confirm you now have four commits total.

### Expected Outcome

Run the following commands and confirm each produces the indicated result:

- [ ] `git log --oneline` shows exactly 4 commits.
- [ ] `git status` shows `nothing to commit, working tree clean`.
- [ ] `git diff HEAD~1 HEAD -- config.py` shows only the `MAX_ENTRIES` line added (not the `LOG_FILE` change).
- [ ] `git show HEAD~2 -- config.py` shows only the `LOG_FILE` path change.
- [ ] `ls` in the project directory confirms `.env` is present on disk but `git log --all --full-history -- .env` returns no output (the file was never committed).

### Hints

- If `git add -p` shows `No changes` or behaves unexpectedly, run `git diff` first to confirm the file actually has unstaged changes.
- If you accidentally stage the wrong hunk, use `git restore --staged config.py` to unstage the entire file and start Part C over from step 14.
- The order of commits matters for the `git diff HEAD~1 HEAD` check: the most recent commit (`HEAD`) must be the `MAX_ENTRIES` commit.

---

## Exercise 2 of 3: Branch, Diverge, Conflict, Resolve

**Difficulty:** Intermediate | **Estimated Time:** 50–70 minutes

### Learning Objectives

By the end of this exercise you will be able to:
- Create two branches that diverge from the same commit and accumulate independent history
- Produce and manually resolve a merge conflict
- Use `git log --oneline --graph --all --decorate` to read branch topology
- Distinguish between a fast-forward merge and a three-way merge commit
- Delete a feature branch safely after its changes are merged

### Scenario

The `devlog` project is growing. You need to add two features simultaneously: a `--search` flag (to find log entries by keyword) and a `--delete` flag (to remove entries). Both features require modifying the same function in `devlog.py` — which will cause a merge conflict. You will create both branches, develop each feature independently, merge the first cleanly, then resolve the conflict that arises when merging the second.

**Start from the repository you built in Exercise 1.** If you did not complete Exercise 1, use the solution project at `GIT/Projects/Solutions/Exercise1-Basic Commands/` as your starting point (copy it to a new directory and continue from there).

### Step-by-Step Instructions

#### Part A: Create Two Diverging Feature Branches

1. Confirm you are on `main` and the working tree is clean:
   ```bash
   git status
   git log --oneline
   ```

2. Create and switch to the search feature branch:
   ```bash
   git checkout -b feature/search
   ```

3. Open `devlog.py`. Find the `run()` function (or the main entry point). Add a comment block and a stub for the search feature — something like:
   ```python
   # --- search feature ---
   def search_entries(keyword):
       """Return all log entries containing keyword."""
       pass
   ```
   Also modify the `run()` function body to include a call or a `TODO` comment referencing `search_entries`. The key requirement is that `run()` itself is modified on this branch.

4. Stage and commit:
   ```bash
   git add devlog.py
   git commit -m "Add search_entries stub and wire into run()"
   ```

5. Switch back to `main` **without** merging yet:
   ```bash
   git checkout main
   ```

6. Create and switch to the delete feature branch **from `main`** (not from `feature/search`):
   ```bash
   git checkout -b feature/delete
   ```

7. Open `devlog.py`. Find the same `run()` function you modified on `feature/search`. Add a different modification — a delete stub and a `TODO` in `run()`:
   ```python
   # --- delete feature ---
   def delete_entry(entry_id):
       """Remove the log entry with the given ID."""
       pass
   ```
   Modify `run()` to reference `delete_entry` in a way that **overlaps with the same lines** you changed on `feature/search`. This overlap is deliberate — it will cause a conflict later.

8. Stage and commit:
   ```bash
   git add devlog.py
   git commit -m "Add delete_entry stub and wire into run()"
   ```

9. View the current branch topology:
   ```bash
   git log --oneline --graph --all --decorate
   ```
   You should see three branches (`main`, `feature/search`, `feature/delete`) fanning out from the same base commit, with `feature/search` and `feature/delete` each having one commit that `main` does not have.

   > **Expected shape:** The graph should show two lines diverging from a single point, not a straight line. If it looks like a straight line, both feature branches may have been created from the same parent — verify with `git log --oneline --all`.

#### Part B: Fast-Forward Merge the First Feature

10. Switch to `main`:
    ```bash
    git checkout main
    ```

11. Check the current state of `main` relative to `feature/search`:
    ```bash
    git log --oneline main..feature/search
    ```
    This shows commits that are in `feature/search` but not in `main`. You should see exactly one commit.

12. Merge `feature/search` using `--no-ff` to force a merge commit even though a fast-forward would be possible:
    ```bash
    git merge --no-ff feature/search -m "Merge feature/search: add keyword search capability"
    ```

    > **Why `--no-ff`?** A fast-forward merge moves the `main` pointer silently, leaving no record in the graph that these commits were developed as a feature. The `--no-ff` flag preserves that context. This matches Best Practice 8 from the module.

13. Confirm the merge commit exists:
    ```bash
    git log --oneline --graph --all --decorate
    ```
    You should now see a merge commit on `main` with two parent lines.

14. Delete the merged branch:
    ```bash
    git branch -d feature/search
    ```

#### Part C: Produce and Resolve a Merge Conflict

15. Now merge `feature/delete` into `main`:
    ```bash
    git merge --no-ff feature/delete
    ```
    Git will report a merge conflict in `devlog.py` because both branches modified overlapping lines in `run()`. The output will look similar to:
    ```
    Auto-merging devlog.py
    CONFLICT (content): Merge conflict in devlog.py
    Automatic merge failed; fix conflicts then commit the result.
    ```

16. Open `devlog.py` in your editor. Find the conflict markers Git inserted:
    ```
    <<<<<<< HEAD
    ... your main/search version of run() ...
    =======
    ... your delete version of run() ...
    >>>>>>> feature/delete
    ```

17. Resolve the conflict by editing the file so that `run()` incorporates **both** the search and delete references. Remove all three conflict marker lines (`<<<<<<<`, `=======`, `>>>>>>>`). The resolved file must be valid Python.

18. Verify the file has no remaining conflict markers:
    ```bash
    grep -n "<<<<<<\|=======\|>>>>>>>" devlog.py
    ```
    This command must produce no output.

19. Stage the resolved file and complete the merge:
    ```bash
    git add devlog.py
    git commit -m "Merge feature/delete: resolve run() conflict, integrate delete capability"
    ```

20. Delete the feature branch:
    ```bash
    git branch -d feature/delete
    ```

21. Run the final topology view:
    ```bash
    git log --oneline --graph --all --decorate
    ```

### Expected Outcome

- [ ] `git log --oneline --graph --all --decorate` shows two merge commits on `main`, each with two parent lines visible in the ASCII graph.
- [ ] `git branch` lists only `main` (both feature branches have been deleted).
- [ ] `grep -n "<<<<<<\|=======\|>>>>>>>" devlog.py` returns no output.
- [ ] `python3 -c "import devlog"` (run from the project directory) exits with no `SyntaxError`.
- [ ] `git log --oneline` on `main` shows at least 6 commits (4 from Exercise 1 + 2 merge commits + 2 feature commits that were merged in).

### Hints

- If you accidentally merge `feature/delete` before creating the conflict, use `git reset --hard HEAD~1` to undo the merge commit (safe to do before pushing anything), then redo the branch work.
- If both features modified completely different lines and no conflict occurs, open `devlog.py` again and manually edit the same line on each branch — the line must literally overlap.
- After resolving a conflict, always run `git status` before `git commit` to confirm the file is staged and no other files are in a conflict state.
- `git merge --abort` cancels an in-progress merge and returns the repository to its pre-merge state, which is useful if you want to start the resolution over.

---

## Exercise 3 of 3: Simulating a Remote Workflow Without GitHub

**Difficulty:** Intermediate / Advanced | **Estimated Time:** 50–70 minutes

### Learning Objectives

By the end of this exercise you will be able to:
- Create and configure a bare repository as a stand-in for a remote host
- Push a local repository to that remote and set upstream tracking
- Clone the repository into a second directory simulating a second machine
- Produce a diverged-history scenario and resolve it using `git pull --rebase`
- Inspect remote-tracking branches with `git branch -a` and `git remote -v`

### Scenario

Your `devlog` project is ready to share. You do not have a GitHub account set up right now, so you will simulate the entire remote workflow using two local directories and a bare repository on your own filesystem. A bare repository (created with `git init --bare`) is exactly what Git hosting services store on their servers — it has no working directory, only the `.git` database. You will push from your original project clone ("machine A"), then clone it to a new directory ("machine B"), make conflicting commits on both machines, and practice the `--rebase` pull strategy to keep the history linear.

**Start from the repository you built in Exercise 2.**

### Step-by-Step Instructions

#### Part A: Create a Bare Repository (Your "Remote")

1. Choose a parent directory outside your existing project. Create a bare repository there:
   ```bash
   mkdir -p ~/git-remotes
   git init --bare ~/git-remotes/devlog.git
   ```
   The `.git` suffix is the conventional name for bare repositories. The directory will contain subdirectories like `branches/`, `objects/`, and `refs/` but no working files.

2. Verify the bare repository was created correctly:
   ```bash
   ls ~/git-remotes/devlog.git
   ```
   You should see `HEAD`, `config`, `description`, `hooks/`, `info/`, `objects/`, and `refs/` — but no `devlog.py`.

#### Part B: Push Your Existing Repository ("Machine A")

3. Navigate back to your `devlog` project directory from Exercise 2.

4. Add the bare repository as a remote named `origin`:
   ```bash
   git remote add origin ~/git-remotes/devlog.git
   ```

5. Verify the remote is configured correctly:
   ```bash
   git remote -v
   ```
   Expected output (paths will vary):
   ```
   origin  /home/yourname/git-remotes/devlog.git (fetch)
   origin  /home/yourname/git-remotes/devlog.git (push)
   ```

6. Push `main` to `origin` and set the upstream tracking branch:
   ```bash
   git push -u origin main
   ```

7. Confirm the push succeeded by listing remote-tracking branches:
   ```bash
   git branch -a
   ```
   You should see `main` (local) and `remotes/origin/main` (remote-tracking).

#### Part C: Clone to a Second Directory ("Machine B")

8. Clone the bare repository into a new directory that simulates a second machine:
   ```bash
   git clone ~/git-remotes/devlog.git ~/devlog-machine-b
   ```

9. Navigate into the cloned directory and verify it has the full history:
   ```bash
   cd ~/devlog-machine-b
   git log --oneline
   ```
   The log should match the one on machine A exactly.

10. On "machine B", make a new commit — for example, add a `CHANGELOG.md` file:
    ```bash
    echo "# Changelog\n\n## Unreleased\n- Search feature\n- Delete feature" > CHANGELOG.md
    git add CHANGELOG.md
    git commit -m "Add initial CHANGELOG"
    ```

11. Push the commit from machine B to the shared remote:
    ```bash
    git push
    ```

#### Part D: Create a Diverged History and Resolve with Rebase

12. Switch back to your **original** project directory (machine A). Do NOT run `git pull` yet.

13. On machine A, make a different commit — for example, update `README.md` with a new section:
    Open `README.md` and add a `## Usage` section at the bottom. Then:
    ```bash
    git add README.md
    git commit -m "Add Usage section to README"
    ```

14. Now try to push from machine A:
    ```bash
    git push
    ```
    Git will reject the push because the remote has a commit (from machine B) that machine A does not have locally. The error will look like:
    ```
    ! [rejected]        main -> main (fetch first)
    error: failed to push some refs to '...'
    hint: Updates were rejected because the remote contains work that you do
    hint: not have locally. Integrate the remote changes (e.g.
    hint: 'git pull ...') before pushing again.
    ```

15. Pull with the rebase strategy to replay machine A's commit on top of the remote's history:
    ```bash
    git pull --rebase origin main
    ```
    Expected output:
    ```
    Successfully rebased and updated refs/heads/main.
    ```

16. View the history to confirm it is linear (no merge commit):
    ```bash
    git log --oneline --graph --all --decorate
    ```
    The graph should be a straight line — the `CHANGELOG.md` commit from machine B appears before the `README.md` commit from machine A, with no merge commit node.

17. Push the rebased history to the remote:
    ```bash
    git push
    ```

18. Switch to the machine B directory and pull to verify both machines are now synchronized:
    ```bash
    cd ~/devlog-machine-b
    git pull
    git log --oneline
    ```
    Machine B should now show the `README.md` commit that machine A produced.

#### Part E: Inspect the Remote Configuration

19. From either directory, run these inspection commands and read their output:
    ```bash
    git remote show origin
    ```
    This shows the remote URL, the tracked branches, and whether your local branch is ahead, behind, or up to date.

    ```bash
    git branch -vv
    ```
    This shows each local branch alongside its remote-tracking counterpart and the ahead/behind count.

20. Verify the final synchronized state:
    ```bash
    git fetch origin
    git status
    ```
    `git status` should report `Your branch is up to date with 'origin/main'.`

### Expected Outcome

- [ ] `git remote -v` (from the machine A directory) shows `origin` pointing to the bare repository path.
- [ ] `git log --oneline` is identical in both the machine A directory and the machine B directory after the final `git pull`.
- [ ] `git log --oneline --graph` shows a **straight line** with no merge commit between the CHANGELOG and README commits — proving the rebase strategy was used.
- [ ] `git branch -a` from either clone shows `remotes/origin/main` as a remote-tracking branch.
- [ ] `ls ~/git-remotes/devlog.git` shows no `devlog.py`, `README.md`, or other working files — confirming the remote is a proper bare repository.

### Hints

- If `git push` is rejected with `non-fast-forward`, you have likely made commits on machine A before pulling. This is the intended scenario in Part D — follow the `git pull --rebase` steps.
- If `git pull --rebase` reports a rebase conflict, resolve it the same way as a merge conflict: edit the file, run `git add <file>`, then run `git rebase --continue` (not `git commit`).
- On Windows, use full absolute paths instead of `~/` notation: `C:/Users/yourname/git-remotes/devlog.git`.
- `git clone` sets up `origin` automatically; `git remote add` is only needed for the original machine A repository (which was not cloned).
- After using `--rebase`, the local commit hash changes because the commit is replayed onto a new parent. This is normal and expected.

### Bonus Challenge (Optional — Requires a GitHub Account)

Replace the bare local repository with a real GitHub remote:

1. Create an empty repository on GitHub (do not initialize it with a README — you already have one locally).
2. On machine A, change the remote URL: `git remote set-url origin https://github.com/yourname/devlog.git`
3. Force-push your full history: `git push -u origin main`
4. Open a second terminal, clone from GitHub into a new directory, make a commit, and push.
5. Return to machine A and practice the full `git pull --rebase && git push` cycle against the real remote.

This bonus challenge requires no changes to your local repository structure — it is purely a URL swap.

---

## Concepts Covered Across All Three Exercises

| Concept | Exercise |
|---|---|
| `git init -b main` | 1 |
| `.gitignore` from first commit | 1 |
| `git status` (tracked / staged / untracked) | 1 |
| `git diff` vs `git diff --staged` vs `git diff HEAD` | 1 |
| `git add -p` (interactive staging) | 1 |
| `git log --oneline` | 1, 2, 3 |
| `git checkout -b` (create + switch) | 2 |
| `git merge --no-ff` | 2 |
| Merge conflict resolution | 2 |
| `git log --oneline --graph --all --decorate` | 2, 3 |
| `git branch -d` | 2 |
| `git init --bare` | 3 |
| `git remote add` / `git remote -v` | 3 |
| `git push -u origin main` | 3 |
| `git clone` | 3 |
| `git pull --rebase` | 3 |
| `git branch -a` | 3 |
| `git branch -vv` | 3 |
