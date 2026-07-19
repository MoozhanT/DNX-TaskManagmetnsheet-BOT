#!/bin/sh
set -e

mkdir -p /root/.ssh
cp /run/secrets/tunnel_key /root/.ssh/id_ed25519
chmod 600 /root/.ssh/id_ed25519

export AUTOSSH_GATETIME=0
export AUTOSSH_POLL=30

exec autossh -M 0 -N \
    -o "StrictHostKeyChecking=no" \
    -o "UserKnownHostsFile=/dev/null" \
    -o "ServerAliveInterval=30" \
    -o "ServerAliveCountInterval=3" \
    -o "ExitOnForwardFailure=yes" \
    -i /root/.ssh/id_ed25519 \
    -D "0.0.0.0:${SOCKS_PORT:-1080}" \
    "${REMOTE_USER:-root}@${REMOTE_HOST}"
