#!/bin/sh
# Deploy the main branch from a separate checkout without touching persistent data.
set -eu
export GIT_TERMINAL_PROMPT=0
app_home=${WEDDING_APP_HOME:-"$HOME/apps/fotos_boda"}
release=${WEDDING_RELEASE_DIR:-"$HOME/apps/fotos_boda-auto"}
state=${WEDDING_DEPLOY_STATE:-"$HOME/.local/state/wedding-deploy/last-success"}
remote=${WEDDING_GIT_REMOTE:-git@github.com:mimove/fotos_boda.git}

for path in "$app_home/.env" "$app_home/files" "$app_home/data"; do
    if [ ! -e "$path" ]; then echo "Missing persistent path: $path" >&2; exit 1; fi
done
mkdir -p "$(dirname "$release")" "$(dirname "$state")"
if [ ! -d "$release/.git" ]; then
    if [ -e "$release" ]; then echo "Release directory already exists: $release" >&2; exit 1; fi
    git clone --branch main --single-branch "$remote" "$release"
fi
for name in .env files data; do
    if [ -L "$release/$name" ]; then
        [ "$(readlink "$release/$name")" = "$app_home/$name" ] || { echo "Unexpected $name link" >&2; exit 1; }
    elif [ -e "$release/$name" ]; then
        echo "Refusing to replace $release/$name" >&2; exit 1
    else
        ln -s "$app_home/$name" "$release/$name"
    fi
done
git -C "$release" fetch origin main
# Do not deploy the original commit: it has no production Compose configuration.
if ! git -C "$release" cat-file -e origin/main:docker-compose.yml 2>/dev/null; then
    echo "Waiting for production configuration to be pushed to main."
    exit 0
fi
if ! git -C "$release" diff --quiet || ! git -C "$release" diff --cached --quiet; then
    echo "Release checkout has local changes; deployment stopped." >&2; exit 1
fi
git -C "$release" merge --ff-only origin/main
commit=$(git -C "$release" rev-parse HEAD)
if [ -f "$state" ] && [ "$(cat "$state")" = "$commit" ]; then exit 0; fi
cd "$release"
docker compose -p fotos_boda up -d --build
attempt=0
until curl -fsS --max-time 5 -o /dev/null http://127.0.0.1:5000/; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 10 ]; then echo "Application health check failed; will retry." >&2; exit 1; fi
    sleep 2
done
printf '%s\n' "$commit" > "$state.tmp"
mv "$state.tmp" "$state"
echo "Deployed $commit"
