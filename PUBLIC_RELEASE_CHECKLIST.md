# Public release checklist

## Before making the repo public

- [ ] Phases 1–4 complete (security posture, docs organized, root cleanup)
- [ ] No live secrets in git history (review with your security tooling; sample commits may mention `sk-ant-` / `ghp_` as **placeholders** only)
- [ ] Tests and smoke checks you rely on are green in CI or locally
- [ ] `README.md` and `LICENSE` / `LICENSE.commercial` read correctly for strangers
- [ ] `SECURITY.md` and disclosure process are current

## Steps to make the repo public

1. Open GitHub: [github.com/pilotmain/aethos/settings](https://github.com/pilotmain/aethos/settings)
2. Scroll to **Danger Zone**
3. **Change repository visibility** → **Public**
4. Confirm

## After going public

- [ ] Fix any broken external links or install URLs
- [ ] Announce where you maintain a presence (blog, social, etc.)
- [ ] Optional: GitHub Pages or a docs site for `docs/`
- [ ] Optional: publish `aethos-core` to PyPI when that package is split

## Stay private

- **`aethos-pro`** (commercial wheels) and other proprietary repos must **remain private**.
