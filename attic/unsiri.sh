#!/bin/bash
# Turns off "Learn from this application" and "Show Siri Suggestions in application"
# for every app, by filling the two exclusion lists the App Access pane reads.
# Usage: siri-app-access-off.sh [--dry-run]

domain=com.apple.suggestions
keys=(SiriCanLearnFromAppBlacklist AppCanShowSiriSuggestionsBlacklist)

current_entries() {
  for key in "${keys[@]}"; do
    defaults read "$domain" "$key" 2>/dev/null | tr -d ' ",()'
  done
}

installed_apps() {
  find /Applications /System/Applications "$HOME/Applications" -name '*.app' 2>/dev/null
  find /System/Library/CoreServices -maxdepth 1 -name '*.app' 2>/dev/null
}

app_bundle_ids() {
  installed_apps | while IFS= read -r app; do
    /usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app/Contents/Info.plist" 2>/dev/null
  done
}

bundle_ids=()
while IFS= read -r bundle_id; do
  bundle_ids+=("$bundle_id")
done < <({ current_entries; app_bundle_ids; } | grep -E '^[A-Za-z0-9._-]+$' | sort -u)

if [[ "$1" == --dry-run ]]; then
  printf '%s\n' "${bundle_ids[@]}"
  echo "${#bundle_ids[@]} bundle IDs"
  exit
fi

for key in "${keys[@]}"; do
  defaults write "$domain" "$key" -array "${bundle_ids[@]}" || exit 1
done
killall suggestd 2>/dev/null
echo "Wrote ${#bundle_ids[@]} bundle IDs to both lists. Reopen System Settings to see the result."
