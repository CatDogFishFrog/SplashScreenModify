#!/usr/bin/env bash
# Writes the GitHub release description for a tag.
#
# Usage: release-notes.sh <tag> <owner/repo> <output file>
# Needs git-cliff on PATH and a checkout with the full history and all tags.
set -euo pipefail

tag="$1"
repository="$2"
output="$3"

previous="$(git describe --tags --abbrev=0 --match 'v[0-9]*' "${tag}^" 2>/dev/null || true)"

# Changes since the previous release; for the very first release, the whole history.
cliff_args=(--config cliff.toml --strip header)
if [[ -n "$previous" ]]; then
  cliff_args+=("${previous}..${tag}")
fi
changelog="$(git-cliff "${cliff_args[@]}")"
changelog="${changelog#"${changelog%%[![:space:]]*}"}"  # drop leading blank lines

{
  echo "Standalone executable for 64-bit Windows. No installation and no Python required."
  echo
  if [[ -n "${changelog//[[:space:]]/}" ]]; then
    printf '%s\n' "$changelog"
  else
    echo "Internal changes only: the behavior of the tool is unchanged."
  fi
  if [[ -n "$previous" ]]; then
    echo
    echo "**Full changelog:** [${previous}...${tag}](https://github.com/${repository}/compare/${previous}...${tag})"
  fi
} > "$output"
