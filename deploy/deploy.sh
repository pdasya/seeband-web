#!/usr/bin/env bash
# Deploys one image tag on the host, checks it, and goes back to the tag before it if the check
# fails. Run it in the directory that holds compose.yaml and .env (the deploy job copies both):
#   ./deploy.sh <tag> <health URL>
# for example ./deploy.sh sha-0123456789ab https://seeband.example/api/health. The tag must be
# one the registry holds; the URL must answer the API's health with this tag's commit.
#
# The tag running now is in .deployed-tag, and the one before it in .previous-tag. To roll back by
# hand: ./deploy.sh "$(cat .previous-tag)" <health URL>.
#
# SEEBAND_DEPLOY_PULL=0 skips pulling, for images already on the machine, as the CI test does.
set -euo pipefail

tag=${1:?usage: deploy.sh <tag> <health URL>}
health_url=${2:?usage: deploy.sh <tag> <health URL>}
export SEEBAND_IMAGE_PREFIX=${SEEBAND_IMAGE_PREFIX:-ghcr.io/pdasya/seeband}
compose=(docker compose -f compose.yaml)

current=$(cat .deployed-tag 2>/dev/null || true)

up() {
  export SEEBAND_TAG=$1
  if [[ ${SEEBAND_DEPLOY_PULL:-1} != 0 ]]; then
    "${compose[@]}" pull --quiet
  fi
  # Waits for the API's own health check, which answers once its workers have started.
  "${compose[@]}" up --detach --no-build --wait --wait-timeout 180
}

# The running API must answer through Caddy, from the image just started: its commit is in the
# tag, sha-<first 12 characters>.
healthy() {
  local commit=${1#sha-} answer
  for _ in $(seq 1 30); do
    if answer=$(curl -fsS --max-time 5 "$health_url" 2>/dev/null); then
      if [[ $1 != sha-* ]] || grep -q "\"commit\":\"$commit\"" <<<"$answer"; then
        return 0
      fi
    fi
    sleep 2
  done
  return 1
}

echo "Deploying $tag (running: ${current:-none})"
if up "$tag" && healthy "$tag"; then
  if [[ -n $current && $current != "$tag" ]]; then
    echo "$current" >.previous-tag
  fi
  echo "$tag" >.deployed-tag
  echo "Deployed $tag"
  exit 0
fi

echo "The check of $tag failed" >&2
if [[ -n $current && $current != "$tag" ]]; then
  echo "Rolling back to $current" >&2
  if up "$current" && healthy "$current"; then
    echo "Rolled back to $current" >&2
  else
    echo "The rollback to $current failed too: the service needs a person" >&2
  fi
fi
exit 1
