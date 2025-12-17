#!/bin/bash
# Generate/update docs-changelog.json from all markdown files in docs/
# Uses Git history for accurate creation/update dates
# Usage: ./scripts/docs-changelog.sh

set -e

CHANGELOG_FILE="docs-changelog.json"

# Always start fresh - remove existing file and create new one
rm -f "$CHANGELOG_FILE"
echo '{"files": {}, "history": []}' > "$CHANGELOG_FILE"
echo "Regenerating $CHANGELOG_FILE..."

TODAY=$(date -u +"%Y-%m-%d")
count=0

echo "Scanning docs folder with Git history..."

for file in $(find docs -name "*.md" -type f 2>/dev/null | sort); do
    # Get relative path from docs/
    REL_PATH="${file#docs/}"

    # Extract title from first heading or use filename
    TITLE=$(head -20 "$file" | grep -m1 '^# ' | sed 's/^# *//' || echo "$REL_PATH")
    if [ -z "$TITLE" ]; then
        TITLE="$REL_PATH"
    fi

    # Check if file already exists in changelog
    EXISTS=$(jq -r --arg path "$REL_PATH" '.files[$path] // empty' "$CHANGELOG_FILE")

    if [ -z "$EXISTS" ]; then
        # New file - use Git history for accurate dates
        # Get creation date (first commit that added this file)
        CREATED=$(git log --follow --format=%aI --reverse -- "$file" 2>/dev/null | head -1 | cut -d'T' -f1)
        if [ -z "$CREATED" ]; then
            CREATED="$TODAY"  # Fallback to today if no Git history
        fi

        # Get last updated date (most recent commit)
        LAST_UPDATED=$(git log --format=%aI -1 -- "$file" 2>/dev/null | cut -d'T' -f1)
        if [ -z "$LAST_UPDATED" ]; then
            LAST_UPDATED="$TODAY"
        fi

        # Count commits to this file
        UPDATE_COUNT=$(git log --follow --oneline -- "$file" 2>/dev/null | wc -l | tr -d ' ')
        if [ -z "$UPDATE_COUNT" ] || [ "$UPDATE_COUNT" -eq 0 ]; then
            UPDATE_COUNT=1
        fi

        # Add to files map with real Git history
        jq --arg path "$REL_PATH" \
           --arg created "$CREATED" \
           --arg updated "$LAST_UPDATED" \
           --argjson count "$UPDATE_COUNT" \
           --arg title "$TITLE" \
           '.files[$path] = {"created": $created, "lastUpdated": $updated, "updateCount": $count, "title": $title}' \
           "$CHANGELOG_FILE" > tmp.json && mv tmp.json "$CHANGELOG_FILE"

        # Calculate days since creation and last update
        DAYS_SINCE_CREATION=$(( ( $(date +%s) - $(date -j -f "%Y-%m-%d" "$CREATED" +%s 2>/dev/null || date +%s) ) / 86400 ))
        DAYS_SINCE_UPDATE=$(( ( $(date +%s) - $(date -j -f "%Y-%m-%d" "$LAST_UPDATED" +%s 2>/dev/null || date +%s) ) / 86400 ))

        # Add to history based on recency
        if [ "$DAYS_SINCE_CREATION" -le 14 ]; then
            # New file (created within 14 days)
            jq --arg path "$REL_PATH" \
               --arg date "$CREATED" \
               --arg type "new" \
               --arg title "$TITLE" \
               '.history = [{"date": $date, "file": $path, "type": $type, "title": $title}] + .history' \
               "$CHANGELOG_FILE" > tmp.json && mv tmp.json "$CHANGELOG_FILE"
            echo "  [new] $REL_PATH (created $CREATED)"
        elif [ "$DAYS_SINCE_UPDATE" -le 7 ] && [ "$LAST_UPDATED" != "$CREATED" ]; then
            # Recently updated (within 7 days, and has been modified since creation)
            jq --arg path "$REL_PATH" \
               --arg date "$LAST_UPDATED" \
               --arg type "updated" \
               --arg title "$TITLE" \
               '.history = [{"date": $date, "file": $path, "type": $type, "title": $title}] + .history' \
               "$CHANGELOG_FILE" > tmp.json && mv tmp.json "$CHANGELOG_FILE"
            echo "  [updated] $REL_PATH (last changed $LAST_UPDATED)"
        else
            echo "  [tracked] $REL_PATH (created $CREATED)"
        fi
        count=$((count + 1))
    else
        # Existing file - check if it needs updating based on Git
        GIT_LAST_UPDATED=$(git log --format=%aI -1 -- "$file" 2>/dev/null | cut -d'T' -f1)
        CHANGELOG_LAST_UPDATED=$(jq -r --arg path "$REL_PATH" '.files[$path].lastUpdated' "$CHANGELOG_FILE")

        if [ -n "$GIT_LAST_UPDATED" ] && [ "$GIT_LAST_UPDATED" != "$CHANGELOG_LAST_UPDATED" ]; then
            # File was updated - increment count
            CURRENT_COUNT=$(jq -r --arg path "$REL_PATH" '.files[$path].updateCount // 1' "$CHANGELOG_FILE")
            NEW_COUNT=$((CURRENT_COUNT + 1))

            jq --arg path "$REL_PATH" \
               --arg date "$GIT_LAST_UPDATED" \
               --argjson count "$NEW_COUNT" \
               --arg title "$TITLE" \
               '.files[$path].lastUpdated = $date | .files[$path].updateCount = $count | .files[$path].title = $title' \
               "$CHANGELOG_FILE" > tmp.json && mv tmp.json "$CHANGELOG_FILE"

            # Add to history
            jq --arg path "$REL_PATH" \
               --arg date "$GIT_LAST_UPDATED" \
               --arg type "updated" \
               --arg title "$TITLE" \
               '.history = [{"date": $date, "file": $path, "type": $type, "title": $title}] + .history' \
               "$CHANGELOG_FILE" > tmp.json && mv tmp.json "$CHANGELOG_FILE"

            echo "  [updated] $REL_PATH (last changed $GIT_LAST_UPDATED)"
            count=$((count + 1))
        fi
    fi
done

# Trim history to last 500 entries
jq '.history = .history[:500]' "$CHANGELOG_FILE" > tmp.json && mv tmp.json "$CHANGELOG_FILE"

echo ""
echo "Done! $count files processed."
echo "Changelog has $(jq '.files | length' $CHANGELOG_FILE) files tracked."
