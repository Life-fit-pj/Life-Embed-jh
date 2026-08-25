# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Project status

This repository is a fresh scaffold, not yet an implemented application. The directory
layout below exists, but the source files in it are currently empty:

- `app/config.py` — empty
- `app/core/` — empty directory
- `app/features/` — empty directory
- `pipeline/prep/` — empty directory
- `src/` — empty directory
- `docu/DESIGN.md` — empty

There is no dependency manifest yet (no `requirements.txt`, `pyproject.toml`, or
`package.json`), and no build, lint, or test tooling has been set up. `.gitignore` is a
standard Python template, so the project is expected to be Python-based once code is
added. Do not assume any framework, package structure, or commands beyond what actually
exists in the repo — check for a manifest/config file before assuming how to
install, run, lint, or test the project, since none of that is established yet.

## Intended architecture (from directory scaffold)

Based on the empty directories already present, the project is structured as:

- `app/` — application layer (`core/` and `features/` subpackages, plus `config.py` for
  configuration)
- `pipeline/prep/` — data preparation / preprocessing pipeline
- `src/` — additional source code
- `data/` — local data files (see note below)
- `docu/` — project design documentation

## Data directory

`data/` is untracked by git. As of this writing it does not contain usable data
(`data/life.db` is present but empty). Do not assume specific schemas, tables, or file
contents in `data/` without inspecting it directly first, as its contents may change or
be absent.
