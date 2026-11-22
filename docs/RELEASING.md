# Releasing

Only the owner releases. Agents never tag, publish or create a release.

## What a release is here

A Git tag on `main`. There is no package, installer or deployment: the application runs from a checkout with `python -m line_editor`.

## Steps

1. Confirm every pull request for the release is merged and CI is green on `main`.
2. Run the test command from `CLAUDE.md` on `main`: `python -m unittest discover -s tests -t .`. Record the test count and `OK`.
3. Move the Unreleased entries in `CHANGELOG.md` under a new version heading with the date. Commit that change through a pull request.
4. Check that the README and `docs/PRD.md` state only measured performance figures (see `CLAUDE.md`, "Hard constraints").
5. The owner tags the merge commit (`vMAJOR.MINOR.PATCH`) and creates the GitHub release from the changelog section.
