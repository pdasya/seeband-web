#!/usr/bin/env bash
# Prepares a fresh Ubuntu 24.04 machine to receive deploys, once, as root:
#   sudo bash host-setup.sh '<deploy public key>' <site address>
# for example sudo bash host-setup.sh 'ssh-ed25519 AAAA… seeband-deploy' 203-0-113-7.sslip.io
#
# It installs Docker from Docker's repository, creates the user `deploy` in the `docker` group
# with only the given key, opens TCP 80 and 443 and UDP 443 in the machine's own firewall, and
# writes /opt/seeband/.env. It changes nothing it finds already done, so it can run again.
# Cloud firewalls outside the machine, such as an Oracle Cloud security list, are opened in
# their own console (deploy/README.md).
set -euo pipefail

key=${1:?usage: host-setup.sh '<deploy public key>' <site address>}
address=${2:?usage: host-setup.sh '<deploy public key>' <site address>}
[[ $(id -u) == 0 ]] || { echo "Run as root, with sudo" >&2; exit 1; }
[[ $key == ssh-* ]] || { echo "The first argument must be an SSH public key" >&2; exit 1; }
[[ $address =~ ^[A-Za-z0-9.-]+$ ]] || { echo "The second argument must be a host name" >&2; exit 1; }

# Oracle's Ubuntu images reject everything but SSH in iptables; open the web ports before that.
# Saved before Docker is installed, so Docker's own chains, which it recreates on each start, are
# not saved with them.
if command -v iptables >/dev/null; then
  for rule in "-p tcp --dport 80" "-p tcp --dport 443" "-p udp --dport 443"; do
    # shellcheck disable=SC2086
    iptables -C INPUT $rule -j ACCEPT 2>/dev/null || iptables -I INPUT $rule -j ACCEPT
  done
  if command -v netfilter-persistent >/dev/null; then
    netfilter-persistent save
  fi
fi

# Docker, from Docker's own repository, as Ubuntu's is older.
if ! command -v docker >/dev/null; then
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc]" \
    "https://download.docker.com/linux/ubuntu $codename stable" >/etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

# The user the deploy job logs in as: only its key, no password.
if ! id deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash deploy
fi
usermod -aG docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
grep -qxF "$key" /home/deploy/.ssh/authorized_keys 2>/dev/null ||
  echo "$key" >>/home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

# The host's settings; the deploy job adds compose.yaml and deploy.sh next to it.
install -d -m 750 -o deploy -g deploy /opt/seeband
if [[ ! -f /opt/seeband/.env ]]; then
  cat >/opt/seeband/.env <<EOF
SEEBAND_SITE_ADDRESS=$address
SEEBAND_HTTP_PORT=80
SEEBAND_HTTPS_PORT=443
EOF
  chown deploy:deploy /opt/seeband/.env
  chmod 600 /opt/seeband/.env
fi

echo "Ready. DEPLOY_USER=deploy, DEPLOY_PATH=/opt/seeband, SEEBAND_PUBLIC_URL=https://$address"
