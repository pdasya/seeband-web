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
# A new Compose file may wait beside the running one as compose.yaml.new, as the deploy job leaves
# it: it replaces compose.yaml for this deploy, and a rollback goes back to the file it replaced.
# After a good deploy, images of other tags than the running and previous ones are removed.
#
# SEEBAND_DEPLOY_PULL=0 skips pulling, for images already on the machine, as the CI test does.
set -euo pipefail

tag=${1:?usage: deploy.sh <tag> <health URL>}
health_url=${2:?usage: deploy.sh <tag> <health URL>}
export SEEBAND_IMAGE_PREFIX=${SEEBAND_IMAGE_PREFIX:-ghcr.io/pdasya/seeband}

current=$(cat .deployed-tag 2>/dev/null || true)

# The Compose file of the running deploy stays for a rollback; without a new one, compose.yaml is
# already the running deploy's.
rm -f .previous-compose.yaml
if [[ -f compose.yaml.new ]]; then
  if [[ -f compose.yaml ]]; then
    cp compose.yaml .previous-compose.yaml
  fi
  mv compose.yaml.new compose.yaml
fi

up() {
  local file=$2
  export SEEBAND_TAG=$1
  if [[ ${SEEBAND_DEPLOY_PULL:-1} != 0 ]]; then
    docker compose -f "$file" pull --quiet
  fi
  # Waits for the API's own health check, which answers once its workers have started.
  docker compose -f "$file" up --detach --no-build --wait --wait-timeout 180
}

# The site's name resolves to this machine, so the check does not depend on the host reaching its
# own public address; Caddy still answers with the site's certificate.
url_host=${health_url#*://}
url_host=${url_host%%/*}
if [[ $url_host != *:* ]]; then
  if [[ $health_url == https://* ]]; then url_host+=":443"; else url_host+=":80"; fi
fi

# The running API must answer through Caddy, from the image just started: its commit is in the
# tag, sha-<first 12 characters>.
healthy() {
  local commit=${1#sha-} answer
  for _ in $(seq 1 30); do
    if answer=$(curl -fsS --max-time 5 --resolve "$url_host:127.0.0.1" "$health_url" 2>/dev/null); then
      if [[ $1 != sha-* ]] || grep -q "\"commit\":\"$commit\"" <<<"$answer"; then
        return 0
      fi
    fi
    sleep 2
  done
  return 1
}

# Removes this deployment's images of tags other than the two kept, and layers left unused.
prune() {
  local keep=("$@") image name
  docker image ls --format '{{.Repository}}:{{.Tag}}' |
    while read -r image; do
      for name in api web; do
        [[ $image == "$SEEBAND_IMAGE_PREFIX-$name:"* ]] || continue
        if [[ " ${keep[*]} " != *" ${image##*:} "* ]]; then
          docker image rm "$image" >/dev/null || true
        fi
      done
    done
  docker image prune --force >/dev/null || true
}

echo "Deploying $tag (running: ${current:-none})"
if up "$tag" compose.yaml && healthy "$tag"; then
  previous=$(cat .previous-tag 2>/dev/null || true)
  if [[ -n $current && $current != "$tag" ]]; then
    previous=$current
    echo "$previous" >.previous-tag
  fi
  echo "$tag" >.deployed-tag
  prune "$tag" "$previous"
  echo "Deployed $tag"
  exit 0
fi

echo "The check of $tag failed" >&2
if [[ -n $current && $current != "$tag" ]]; then
  echo "Rolling back to $current" >&2
  rollback_file=compose.yaml
  if [[ -f .previous-compose.yaml ]]; then
    rollback_file=.previous-compose.yaml
  fi
  if up "$current" "$rollback_file" && healthy "$current"; then
    # compose.yaml again describes what runs, for the next deploy and its rollback.
    if [[ $rollback_file != compose.yaml ]]; then
      mv "$rollback_file" compose.yaml
    fi
    echo "Rolled back to $current" >&2
  else
    echo "The rollback to $current failed too: the service needs a person" >&2
  fi
fi
exit 1
