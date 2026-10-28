# Maintain the homepage

For maintainers changing the public homepage or enabling its deployment.
The site is English, dark by default, and requires only Python 3.11+ to build.

From the repository root:

```sh
python3 scripts/build_site.py --output _site --dry-run
python3 scripts/build_site.py --output _site
python3 -m http.server 8000 --directory _site
```

Open `http://localhost:8000`. Edit `site/` for layout, styles, and interactions.
Skill cards and category counts come from `skills.json`; update the skill
sources and regenerate the manifest rather than editing the generated HTML.
Search and agent selection enhance the page; all skills and install commands
remain readable without JavaScript. Assets use relative paths for project Pages.

Once, an owner or maintainer selects **Settings → Pages → Build and deployment
→ Source → GitHub Actions**. After merge, `.github/workflows/pages.yml` builds
and publishes on every push to `main`. PRs build and test without deploying.
The expected URL is `https://fabiandistler.github.io/agents/`.
See [GitHub's workflow requirements](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

The Homepage workflow checks manifest freshness and build contracts. Installation
examples must follow `docs/install.md` when distribution channels change.
