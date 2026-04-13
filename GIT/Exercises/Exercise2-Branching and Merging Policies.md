# Exercise 2: Branching and Merging Policies
> Subject: GIT | Module: 2 — Branching and Merging Policies | Estimated Time: 2.5–3.5 hours

---

## Overview

This exercise set contains two progressively challenging exercises built around `inventory-api` — a small back-end service that manages a product inventory. You will carry the same repository forward from Exercise 1 into Exercise 2, simulating a real team development timeline.

You will NOT repeat the examples from the module. Instead, you will apply branching and merging strategies to situations that require deliberate decisions: which strategy to reach for, why, and how to verify the result.

**Prerequisites:**
- Git 2.40 or later (`git --version`)
- Module 2 read in full
- No GitHub account is required for either exercise (GitHub bonus steps are clearly marked optional)
- No Node.js installation required — the `.js` files are plain text for this exercise

---

## Exercise 1 of 2: Git Flow Hotfix With a Stash Escape Hatch

**Difficulty:** Intermediate | **Estimated Time:** 60–75 minutes

### Learning Objectives

By the end of this exercise you will be able to:
- Apply the Git Flow branching model to a realistic scenario involving a production emergency
- Use `git switch -c` to create branches from specific starting points
- Use `git stash push -u` and `git stash pop` to safely context-switch mid-feature
- Merge a hotfix branch into both `main` and `develop` using `--no-ff`, preserving branch topology in the log
- Tag a release commit on `main` using annotated tags
- Use `git branch --merged` to identify and clean up stale branches

### Scenario

You are a developer on the `inventory-api` team. You are halfway through building a new `feature/low-stock-alerts` feature on the `develop` branch — you have edited `alerts.js` but have not yet committed your work. Your team lead sends an urgent message: a bug in `api/products.js` is returning a negative stock count when a deletion and an update arrive simultaneously. This bug is on `main` (production). You must fix it immediately without contaminating `main` with your unfinished alerts work.

The starter project in `GIT/Projects/Starters/Exercise2-Branching and Merging Policies/` contains the source files. You will initialize the repository yourself and build the branch history through the steps below.

### Step-by-Step Instructions

#### Part A: Set Up the Git Flow Repository Structure

1. Open a terminal and navigate to the starter project directory:
   ```
   GIT/Projects/Starters/Exercise2-Branching and Merging Policies/
   ```

2. Initialize the repository and make the first commit on `main`:
   ```bash
   git init -b main
   git add .
   git commit -m "Initial commit: inventory-api v1.0.0 baseline"
   ```

3. Tag this commit as the `v1.0.0` release using an annotated tag:
   ```bash
   git tag -a v1.0.0 -m "Release v1.0.0: initial production deployment"
   ```

4. Create and switch to the `develop` branch from `main`. In Git Flow, `develop` is the long-lived integration branch:
   ```bash
   git switch -c develop
   ```

5. Make one commit on `develop` to simulate prior integration work:
   ```bash
   # Edit config.js: change the LOG_LEVEL line from "info" to "debug"
   # (open config.js in your editor and make that change)
   git add config.js
   git commit -m "config: enable debug logging on develop for integration testing"
   ```

6. Run `git log --oneline --graph --all --decorate` and confirm you see:
   - `develop` one commit ahead of `main`
   - `main` and `v1.0.0` tag pointing at the same initial commit

#### Part B: Start a Feature Branch, Then Get Interrupted

7. Create a feature branch from `develop` using `git switch`:
   ```bash
   git switch -c feature/low-stock-alerts develop
   ```

8. Begin editing `alerts.js` — open the file and add the following line at the bottom, but **do not stage or commit it**:
   ```js
   // TODO: implement sendLowStockAlert(productId, currentQty)
   ```
   You now have an unstaged, in-progress change. This is the unfinished work you must protect.

9. Verify `git status` shows the change as modified but unstaged.

10. An urgent Slack message arrives: the stock-count bug is live in production. You need to leave this branch without committing incomplete work. Stash your changes, including the message so you can find it later:
    ```bash
    git stash push -u -m "WIP: low-stock-alerts stub in alerts.js"
    ```

11. Confirm `git status` is clean and the stash was saved:
    ```bash
    git stash list
    ```
    You should see one stash entry with your message.

    > **Hint:** The `-u` flag includes untracked files. If `alerts.js` were a brand-new file you had never staged, omitting `-u` would leave it behind when you switch branches.

#### Part C: Apply the Hotfix

12. Switch to `main` — this is the branch that matches production:
    ```bash
    git switch main
    ```

13. Create the hotfix branch from `main`. In Git Flow, hotfix branches always branch from `main`, not `develop`:
    ```bash
    git switch -c hotfix/negative-stock-count main
    ```

14. Open `api/products.js`. Find the `deleteProduct` function (near the bottom of the file). The current code does not guard against the stock going negative. Replace the body of `deleteProduct` with the corrected version shown in the comment inside the file. The fix should prevent the return value from going below zero.

    > **Hint:** Look for the `// BUGFIX NEEDED` comment in `api/products.js`. The fix is a one-line guard using `Math.max(0, ...)`.

15. Stage and commit the fix:
    ```bash
    git add api/products.js
    git commit -m "fix: prevent negative stock count on concurrent delete+update (#42)"
    ```

16. Run `git log --oneline --graph --all --decorate` and confirm the hotfix branch is one commit ahead of `main`, while `develop` and the feature branch are untouched.

#### Part D: Merge the Hotfix Into Both main and develop

17. Merge the hotfix into `main` using `--no-ff` so the merge commit makes the hotfix visible as a unit in the log:
    ```bash
    git switch main
    git merge --no-ff hotfix/negative-stock-count -m "Merge hotfix/negative-stock-count into main"
    ```

18. Tag the new production release:
    ```bash
    git tag -a v1.0.1 -m "Release v1.0.1: fix negative stock count on concurrent operations"
    ```

19. Merge the hotfix into `develop` so the fix is also present in future development. Use `--no-ff` again:
    ```bash
    git switch develop
    git merge --no-ff hotfix/negative-stock-count -m "Merge hotfix/negative-stock-count into develop"
    ```

20. Delete the hotfix branch — it has been merged into both permanent branches:
    ```bash
    git branch -d hotfix/negative-stock-count
    ```

    > **Hint:** `git branch -d` (lowercase) is safe — Git will refuse to delete if the branch has unmerged commits. If it refuses, you may have skipped one of the merges above.

#### Part E: Resume the Feature

21. Switch back to your feature branch:
    ```bash
    git switch feature/low-stock-alerts
    ```

22. Re-apply your stashed work:
    ```bash
    git stash pop
    ```

23. Confirm `git status` shows your in-progress change to `alerts.js` is back in the working directory.

24. Complete the alert stub: open `alerts.js` and replace the TODO comment you added in step 8 with the following function body:
    ```js
    function sendLowStockAlert(productId, currentQty) {
      console.log(`[ALERT] Product ${productId} has low stock: ${currentQty} units remaining.`);
    }

    module.exports = { sendLowStockAlert };
    ```

25. Stage and commit the feature work:
    ```bash
    git add alerts.js
    git commit -m "feat: add sendLowStockAlert function for low-inventory notifications"
    ```

26. Run the final log to see the complete Git Flow topology:
    ```bash
    git log --oneline --graph --all --decorate
    ```

### Expected Outcome Checklist

Verify each item before moving on to Exercise 2:

- [ ] `git log --oneline --graph --all --decorate` shows `main` and `develop` as permanent branches; the `hotfix/*` branch is absent (deleted)
- [ ] `git tag` lists both `v1.0.0` and `v1.0.1`; running `git show v1.0.1` shows the annotated tag message
- [ ] `git log --oneline main` contains a merge commit whose message references `hotfix/negative-stock-count`
- [ ] `git log --oneline develop` also contains a merge commit bringing the hotfix into `develop`
- [ ] `api/products.js` on `main` contains the `Math.max(0, ...)` guard in `deleteProduct`
- [ ] `alerts.js` on `feature/low-stock-alerts` contains the `sendLowStockAlert` function
- [ ] `git stash list` is empty (the stash was consumed by `git stash pop`)
- [ ] `git branch --merged main` does NOT show the feature branch (it has not been merged into `main` yet)

### Hints

- If `git stash pop` reports a conflict, it means the file changed on the branch since you stashed. Use `git status` to see which file is conflicted, resolve it manually, then `git add` and `git stash drop stash@{0}` to clean up.
- If you forget which commit `v1.0.0` points to, use `git rev-parse v1.0.0` to get the hash and compare it with `git log --oneline main`.
- You can re-run `git log --oneline --graph --all --decorate` after any step to see the evolving topology. Getting comfortable reading that graph is one of the main goals of this exercise.

---

## Exercise 2 of 2: Squash Merges and Three-Way Conflict Resolution

**Difficulty:** Intermediate+ | **Estimated Time:** 75–90 minutes

### Learning Objectives

By the end of this exercise you will be able to:
- Deliberately trigger and methodically resolve a three-way merge conflict using conflict markers
- Choose between fast-forward, `--no-ff`, and `--squash` merge strategies and justify the choice
- Use `git log --oneline --graph` to verify that the chosen merge strategy produced the expected history shape
- Use `git branch --no-merged` to audit unmerged branches
- Use `git restore --staged` to undo a mistaken `git add` during a conflict resolution

### Scenario

Continuing from Exercise 1, you and a colleague are each working on separate branches that both modify `config.js`. Your colleague's branch (`feature/rate-limiting`) was opened first and has three commits in it — including two "wip" commits that would clutter `main`'s history. Your branch (`feature/request-logging`) has one clean commit. Both branches need to land on `develop` today. You will:

1. Merge your clean single-commit branch using a standard `--no-ff` merge
2. Resolve the three-way conflict that results when your colleague's branch is merged afterward
3. Squash your colleague's three noisy commits into one clean commit before it reaches `develop`

### Step-by-Step Instructions

#### Part A: Build the Two Competing Branches

This exercise continues from the repository you built in Exercise 1. You should be on `feature/low-stock-alerts`. Switch to `develop` first:

```bash
git switch develop
```

1. Create your branch from `develop`:
   ```bash
   git switch -c feature/request-logging develop
   ```

2. Open `config.js`. Add the following block at the bottom of the file, after the last existing line:
   ```js
   // Request logging settings
   const REQUEST_LOG_ENABLED = true;
   const REQUEST_LOG_FORMAT = "combined";
   ```

3. Stage and commit:
   ```bash
   git add config.js
   git commit -m "feat: add request logging configuration"
   ```

4. Switch back to `develop` and create your colleague's branch:
   ```bash
   git switch develop
   git switch -c feature/rate-limiting develop
   ```

5. This branch will have three commits to simulate noisy development. Start with the first:
   - Open `config.js` and add the following block at the bottom (after the last existing line — do NOT include the request-logging lines, which belong to the other branch):
     ```js
     // Rate limiting settings
     const RATE_LIMIT_WINDOW_MS = 60000;
     ```
   - Commit it:
     ```bash
     git add config.js
     git commit -m "wip: start rate limiting config"
     ```

6. Make a second commit on the same branch — a common "wip" commit:
   - Open `config.js` and add a new line below the one you just added:
     ```js
     const RATE_LIMIT_MAX_REQUESTS = 100;
     ```
   - Commit it:
     ```bash
     git add config.js
     git commit -m "wip: add max requests constant"
     ```

7. Make the third and final commit — the one that actually completes the feature:
   - Open `config.js` and add the final line below the previous one:
     ```js
     const RATE_LIMIT_MESSAGE = "Too many requests, please try again later.";
     ```
   - Commit it:
     ```bash
     git add config.js
     git commit -m "feat: complete rate limiting configuration with user-facing message"
     ```

8. Run `git log --oneline --graph --all --decorate` and verify:
   - `feature/rate-limiting` is three commits ahead of `develop`
   - `feature/request-logging` is one commit ahead of `develop`
   - Both branches share the same `develop` base commit

#### Part B: Merge the Clean Branch First

9. Switch to `develop`:
   ```bash
   git switch develop
   ```

10. Merge `feature/request-logging` using `--no-ff` to preserve it as a named unit in the history:
    ```bash
    git merge --no-ff feature/request-logging -m "Merge feature/request-logging into develop"
    ```
    This should succeed with no conflicts — the branch only touched lines that `develop` has not touched.

11. Confirm `config.js` on `develop` now contains the `REQUEST_LOG_ENABLED` and `REQUEST_LOG_FORMAT` lines.

12. Delete the merged branch:
    ```bash
    git branch -d feature/request-logging
    ```

#### Part C: Squash-Merge the Noisy Branch

The three commits on `feature/rate-limiting` contain two "wip" messages that you do not want in `develop`'s log. Use a squash merge to collapse them into a single, well-described commit.

13. Verify the branch has three commits that are not in `develop`:
    ```bash
    git log --oneline develop..feature/rate-limiting
    ```
    You should see three lines of output.

14. Run the squash merge. This stages all of the branch's changes but does NOT create a commit automatically:
    ```bash
    git merge --squash feature/rate-limiting
    ```

    Expected output:
    ```
    Squashing commit ...
    Automatic merge went wrong; fix conflicts and then commit the result.
    ```
    OR if there is no conflict:
    ```
    Squashing commit ...
    Automatic merge failed; fix conflicts and then commit the result.
    ```

    > Note: Whether you see a conflict depends on the exact lines added. Proceed to Part D to handle the conflict scenario, which is the expected path for this exercise.

#### Part D: Resolve the Three-Way Conflict

After the squash merge attempt, `config.js` will have conflict markers because both branches appended lines near the end of the file.

15. Run `git status` to confirm the conflict:
    ```bash
    git status
    ```
    You should see `config.js` listed under "both modified" or "modified".

16. Open `config.js` in your editor. You will see conflict markers similar to:
    ```
    <<<<<<< HEAD
    // Request logging settings
    const REQUEST_LOG_ENABLED = true;
    const REQUEST_LOG_FORMAT = "combined";
    =======
    // Rate limiting settings
    const RATE_LIMIT_WINDOW_MS = 60000;
    const RATE_LIMIT_MAX_REQUESTS = 100;
    const RATE_LIMIT_MESSAGE = "Too many requests, please try again later.";
    >>>>>>> feature/rate-limiting
    ```

17. The correct resolution is to keep BOTH blocks — they are independent features. Delete all three conflict marker lines (`<<<<<<<`, `=======`, `>>>>>>>`) and leave the content from both sides. Your resolved `config.js` should end with both the request-logging block and the rate-limiting block, with a blank line between them.

    > **Hint:** Do not use `git checkout --ours` or `git checkout --theirs` here — both would discard one feature entirely. Manual editing is the right tool when both sides must be preserved.

18. After saving, confirm the file looks correct by reviewing it in your editor (no marker characters should remain).

19. You realize you accidentally staged a different file before fixing the conflict. Practice using `git restore --staged` to undo a mistaken staging:
    ```bash
    # Simulate the mistake: stage alerts.js even though you don't mean to
    git add alerts.js
    git status   # notice alerts.js is staged

    # Undo the mistaken staging
    git restore --staged alerts.js
    git status   # alerts.js is no longer staged
    ```

20. Now stage the properly resolved `config.js`:
    ```bash
    git add config.js
    ```

21. Commit with a single, clean message that describes the entire feature (replacing the three noisy "wip" commits):
    ```bash
    git commit -m "feat: add rate limiting configuration (window, max requests, error message)"
    ```

#### Part E: Audit and Clean Up

22. Inspect the final `develop` log:
    ```bash
    git log --oneline --graph develop
    ```
    You should see:
    - One commit for the squash-merged rate-limiting feature (no merge commit node — squash merges do not create merge commits)
    - One merge commit node for the `--no-ff` request-logging merge
    - The prior `develop` and hotfix history from Exercise 1

23. Confirm the `feature/rate-limiting` branch is NOT shown as merged (squash merges do not move the branch pointer into the target's ancestry):
    ```bash
    git branch --no-merged develop
    ```
    `feature/rate-limiting` should appear in this list. This is expected and correct behavior for squash merges.

24. Because the squash merge captures the changes but not the branch ancestry, you must force-delete the branch:
    ```bash
    git branch -D feature/rate-limiting
    ```

25. Run a final audit:
    ```bash
    git branch --no-merged develop
    ```
    Only `feature/low-stock-alerts` (from Exercise 1) should appear — it has not been merged into `develop` yet.

26. Run the full topology view one last time:
    ```bash
    git log --oneline --graph --all --decorate
    ```
    Trace the lines and identify: the `main` branch, the `v1.0.0` and `v1.0.1` tags, the `develop` branch, and the `feature/low-stock-alerts` branch.

### Expected Outcome Checklist

- [ ] `git log --oneline develop` shows exactly one commit for the rate-limiting feature (not three)
- [ ] `git log --oneline develop` shows a merge commit node for `feature/request-logging`
- [ ] `config.js` on `develop` contains all six constants: `LOG_LEVEL`, `REQUEST_LOG_ENABLED`, `REQUEST_LOG_FORMAT`, `RATE_LIMIT_WINDOW_MS`, `RATE_LIMIT_MAX_REQUESTS`, and `RATE_LIMIT_MESSAGE`
- [ ] `config.js` contains no conflict marker characters (`<<<<<<<`, `=======`, `>>>>>>>`)
- [ ] `git branch` lists only `main`, `develop`, and `feature/low-stock-alerts` (all other branches deleted)
- [ ] `git tag` still lists `v1.0.0` and `v1.0.1` (tags are unaffected by branch cleanup)
- [ ] `git log --oneline --graph --all --decorate` shows a non-linear graph (due to the `--no-ff` merge commit from the request-logging branch)

### Hints

- If you are unsure what a squash merge committed to the staging area, use `git diff --cached` before committing to preview the staged changes.
- If your conflict markers look different from the example above (e.g., the blocks are in a different order), that is fine — the content on both sides of `=======` will be the same, just swapped. Keep both blocks regardless of which is `HEAD` and which is the incoming branch.
- `git branch --no-merged` and `git branch --merged` are your best tools for auditing branch status. Run them whenever you are unsure which branches still need attention.
- After a squash merge, always use `git branch -D` (uppercase D) to delete the source branch — `git branch -d` will refuse because the branch's commits are not in the target's ancestry graph.

---

## Bonus Challenges (Optional)

These steps require a GitHub account and are entirely optional. They extend the exercises to cover branch protection rules from Module 2.

### Bonus A: Branch Protection on main

1. Push your completed repository to a new GitHub repository:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/inventory-api.git
   git push -u origin main
   git push origin develop
   git push --tags
   ```

2. In GitHub, navigate to Settings → Branches → Add branch protection rule.
3. Apply the following settings to `main`:
   - Pattern: `main`
   - Enable: "Require a pull request before merging"
   - Set required approvals to 1
   - Enable: "Do not allow bypassing the above settings"
4. Attempt a direct push to `main`:
   ```bash
   echo "# test" >> README.md
   git add README.md
   git commit -m "test: attempt direct push to protected main"
   git push origin main
   ```
   Expected result: GitHub rejects the push with a message about branch protection.

### Bonus B: CODEOWNERS File

1. Create a `.github/CODEOWNERS` file in your repository:
   ```
   # All changes to the api/ directory require review from you
   /api/    @YOUR_GITHUB_USERNAME
   ```

2. Push the file to `develop` (via a feature branch and PR, since `main` is now protected):
   ```bash
   git switch develop
   git switch -c feature/add-codeowners
   mkdir -p .github
   # create .github/CODEOWNERS with the content above
   git add .github/CODEOWNERS
   git commit -m "chore: add CODEOWNERS to protect api/ directory"
   git push origin feature/add-codeowners
   ```

3. Open a pull request targeting `develop` on GitHub and observe that you are automatically added as a required reviewer.
