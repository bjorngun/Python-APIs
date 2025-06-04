#!/usr/bin/env bash
set -eu

PART="${1:-patch}"

CURRENT_VERSION=$(grep -Po 'version\s*=\s*["'\'']\K[0-9]+\.[0-9]+\.[0-9]+' pyproject.toml)
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

case "$PART" in
  major)
    MAJOR=$((MAJOR + 1))
    MINOR=0
    PATCH=0
    ;;
  minor)
    MINOR=$((MINOR + 1))
    PATCH=0
    ;;
  patch)
    PATCH=$((PATCH + 1))
    ;;
  *)
    echo "Invalid version bump: $PART"
    exit 1
    ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"

sed -i "s/version = \"${CURRENT_VERSION}\"/version = \"${NEW_VERSION}\"/" pyproject.toml

echo "Bumped $PART version: $CURRENT_VERSION -> $NEW_VERSION"
echo "new_version=$NEW_VERSION" >> "$GITHUB_OUTPUT"
echo "bump_type=$PART" >> "$GITHUB_OUTPUT"
