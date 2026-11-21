#!/usr/bin/env bash
# Prepares a fresh Ubuntu 24.04 machine to receive deploys, once, as root:
#   sudo bash host-setup.sh '<deploy public key>' <site address>
# for example sudo bash host-setup.sh 'ssh-ed25519 AAAA… seeband-deploy' 203-0-113-7.sslip.io
#
# Run it with sudo as an admin who logs in by key, such as ubuntu: root's SSH login is turned off.
# It installs Docker from Docker's repository, creates the user `deploy` in the `docker` group
# with only the given key, opens TCP 80 and 443 and UDP 443 in the machine's own firewall, turns
# on security updates with a nightly reboot when one needs it, refuses SSH passwords, and writes
# /opt/seeband/.env. It changes nothing it finds already done, so it can run again.
# Cloud firewalls outside the machine, such as an Oracle Cloud security list, are opened in
# their own console (deploy/README.md).
set -euo pipefail

key=${1:?usage: host-setup.sh '<deploy public key>' <site address>}
address=${2:?usage: host-setup.sh '<deploy public key>' <site address>}
[[ $(id -u) == 0 ]] || { echo "Run as root, with sudo" >&2; exit 1; }
[[ $key == ssh-* ]] || { echo "The first argument must be an SSH public key" >&2; exit 1; }
[[ $address =~ ^[A-Za-z0-9.-]+$ ]] || { echo "The second argument must be a host name" >&2; exit 1; }
# Root's SSH login is turned off below, so the admin who runs this must log in by key and use sudo.
admin=${SUDO_USER:-}
if [[ -z $admin || $admin == root ]] || ! id -nG "$admin" | grep -qw sudo ||
  [[ ! -s $(getent passwd "$admin" | cut -d: -f6)/.ssh/authorized_keys ]]; then
  echo "Run with sudo as a user in the sudo group who logs in by SSH key, such as ubuntu" >&2
  exit 1
fi

# Oracle's Ubuntu images reject everything but SSH in iptables; open the web ports before that.
# The filter table is saved only when a rule was added, and without Docker's chains, which Docker
# recreates on each start; restored stale, they would get in its way.
if command -v iptables >/dev/null; then
  added=0
  for rule in "-p tcp --dport 80" "-p tcp --dport 443" "-p udp --dport 443"; do
    # shellcheck disable=SC2086
    if ! iptables -C INPUT $rule -j ACCEPT 2>/dev/null; then
      iptables -I INPUT $rule -j ACCEPT
      added=1
    fi
  done
  if [[ $added == 1 && -d /etc/iptables ]]; then
    iptables-save -t filter | grep -vE 'DOCKER|docker0|br-' >/etc/iptables/rules.v4
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

# The user the deploy job logs in as: only its key, no password. A run with a new key replaces the
# old one, which as a member of the docker group would otherwise stay root-equivalent.
if ! id deploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash deploy
fi
usermod -aG docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
printf '%s\n' "$key" >/home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys

# Security updates every day, and a reboot at 04:00 UTC when an update needs one, such as a new
# kernel. The reboot time is the system's, so the system runs on UTC. Docker starts at boot and
# brings the stack back (restart: unless-stopped); a fit or a deploy running then ends. Only
# Ubuntu's own updates install this way: Docker's packages are upgraded by hand (deploy/README.md).
timedatectl set-timezone Etc/UTC
apt-get install -y unattended-upgrades
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
cat >/etc/apt/apt.conf.d/52seeband-reboot <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
EOF
systemctl enable --now unattended-upgrades

# Keys only, as cloud images usually set already; this keeps it so on any image. sshd takes the
# first value it reads, and reads sshd_config.d in name order, so this file comes first. It stays
# only if sshd accepts it, as a broken one would stop sshd at the next boot.
dropin=/etc/ssh/sshd_config.d/00-seeband.conf
printf '%s\n' "PasswordAuthentication no" "KbdInteractiveAuthentication no" "PermitRootLogin no" \
  >"$dropin"
if ! sshd -t; then
  rm -f "$dropin"
  echo "sshd rejects $dropin; it was removed and sshd is unchanged" >&2
  exit 1
fi
rm -f /etc/ssh/sshd_config.d/60-seeband.conf
effective=$(sshd -T)
for setting in "passwordauthentication no" "kbdinteractiveauthentication no" "permitrootlogin no"; do
  if ! grep -qx "$setting" <<<"$effective"; then
    echo "sshd does not apply '$setting'; check /etc/ssh/sshd_config and its drop-ins" >&2
    exit 1
  fi
done
systemctl reload ssh

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
