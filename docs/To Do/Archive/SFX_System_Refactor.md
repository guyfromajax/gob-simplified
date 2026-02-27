# SFX System Refactor: Git LFS for Audio

**Goal:** Store sound assets in Git LFS so the repo stays manageable as we add more (and larger) audio. No change to how the app references files—paths stay the same.

---

## 1. Install Git LFS

- **macOS:** `brew install git-lfs`
- **Windows:** [git-lfs.com](https://git-lfs.com) — download installer
- **Linux:** `sudo apt install git-lfs` (or equivalent)

Then run once per machine:

```bash
git lfs install
```

---

## 2. Configure LFS for sound files

Create or edit `.gitattributes` in the repo root. Add:

```
# Sound assets — track with LFS
FrontEnd/static/sounds/*.mp3 filter=lfs diff=lfs merge=lfs -text
FrontEnd/static/sounds/*.wav filter=lfs diff=lfs merge=lfs -text
FrontEnd/static/sounds/*.ogg filter=lfs diff=lfs merge=lfs -text
```

This makes all `.mp3`, `.wav`, and `.ogg` under `FrontEnd/static/sounds/` use LFS. Add other extensions there if needed (e.g. `.m4a`).

---

## 3. Migrate existing sounds to LFS

If `FrontEnd/static/sounds/` already has committed files, move them into LFS so history is consistent:

```bash
git lfs migrate import --include="FrontEnd/static/sounds/*.mp3,FrontEnd/static/sounds/*.wav,FrontEnd/static/sounds/*.ogg" --everything
```

- `--everything` rewrites all branches/commits so those paths use LFS. **This rewrites history.** If others have cloned the repo, they must re-clone or follow a force-pull flow after you push.
- If the sounds folder has never been committed, skip this step—new adds will use LFS automatically.

---

## 4. Commit and push

```bash
git add .gitattributes
# If you ran migrate, add any changed files; otherwise just .gitattributes
git add FrontEnd/static/sounds/
git status   # sanity check
git commit -m "Use Git LFS for sound assets"
git push
```

If you ran `git lfs migrate`, use your normal process for pushing rewritten history (e.g. `git push --force-with-lease` on affected branches after coordinating with the team).

---

## 5. Verify (optional)

- **After push:** On GitHub/GitLab, open a file under `FrontEnd/static/sounds/` and confirm it shows an LFS pointer (small file) or a "Stored with Git LFS" badge.
- **Fresh clone:** `git clone <repo>` then `git lfs pull` (or clone with `GIT_LFS_SKIP_SMUDGE=0`). Confirm `FrontEnd/static/sounds/*.mp3` (etc.) are real audio files, not pointer blobs.

---

## Checklist

- [ ] Install `git-lfs` and run `git lfs install`
- [ ] Add LFS rules to `.gitattributes` for `FrontEnd/static/sounds/*.{mp3,wav,ogg}`
- [ ] If sounds already committed: run `git lfs migrate import ... --everything`; coordinate history rewrite with team
- [ ] Commit `.gitattributes` (and migrated files if any); push
- [ ] Confirm LFS in host UI and/or with a fresh clone + `git lfs pull`

---

## Notes

- **Paths unchanged.** Code and docs keep using paths like `/static/sounds/foo.mp3` or `sounds/foo.mp3`. No code changes required for LFS.
- **New files.** Any new `.mp3`/`.wav`/`.ogg` under `FrontEnd/static/sounds/` will be tracked by LFS automatically once `.gitattributes` is in place.
- **Other folders.** To use LFS elsewhere (e.g. music in another directory), add matching lines to `.gitattributes`.
