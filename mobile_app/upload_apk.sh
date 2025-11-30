#!/usr/bin/env bash
set -euo pipefail

# Simple helper to upload the latest release APK to the backend admin endpoint.
# Usage: ./upload_apk.sh http://backend-host:8000 admin@example.com password
# The script reads the APK from build/app/outputs/flutter-apk/app-release.apk.

BACKEND_URL="${1:-}"
EMAIL="${2:-}"
PASSWORD="${3:-}"
APK_PATH="build/app/outputs/flutter-apk/app-release.apk"

if [[ -z "$BACKEND_URL" || -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "Usage: $0 <backend_url> <email> <password>" >&2
  exit 1
fi

if [[ ! -f "$APK_PATH" ]]; then
  echo "APK not found at $APK_PATH. Run 'flutter build apk --release' first." >&2
  exit 1
fi

# Login to get bearer token
TOKEN=$(curl -sS -X POST "$BACKEND_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}" | jq -r '.access_token')

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "Failed to obtain access token. Check credentials and backend URL." >&2
  exit 1
fi

echo "Uploading $APK_PATH to $BACKEND_URL/admin/mobile-apk ..."

curl -sS -X POST "$BACKEND_URL/admin/mobile-apk" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@${APK_PATH};type=application/vnd.android.package-archive" \
  || { echo "Upload failed"; exit 1; }

echo
echo "Upload complete."
