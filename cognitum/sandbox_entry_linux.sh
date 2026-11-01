#!/bin/sh
# Linux-only namespace jail. THIS MUST RUN ONLY UNDER unshare's fresh
# user + mount + PID + network + IPC + UTS namespaces, with --kill-child.
# The host passes these paths, never model data. No fallback on failure.
set -eu
if [ "$#" -ne 3 ]; then exit 90; fi
ROOT="$1"; CODE="$2"; RUNTIME="$3"
# Prove namespace creation occurred: user root mapping is a single outer UID.
# This also prevents accidental execution as an unsandboxed script.
if [ "$(/usr/bin/awk 'NR==1 {print $1}' /proc/self/uid_map)" != 0 ]; then exit 91; fi
# Refuse to run if network or pid namespace is still inherited from pid 1
# in a normal host. No host fallback may be selected by this script.
if [ "$$" -ne 1 ]; then exit 92; fi
# A private tmpfs is the only writable filesystem. Bind immutable allowlisted
# runtime trees, not the host home directory or Cognitum user data.
/usr/bin/mount -t tmpfs -o size=24m,nosuid,nodev,mode=0755 tmpfs "$ROOT"
for x in usr lib lib64 runtime app/cognitum dev tmp; do
    /usr/bin/mkdir -p "$ROOT/$x"
done
for x in usr lib lib64; do
    /usr/bin/mount --bind "/$x" "$ROOT/$x"
    /usr/bin/mount -o remount,bind,ro,nosuid,nodev "$ROOT/$x"
done
/usr/bin/mount --bind "$RUNTIME" "$ROOT/runtime"
/usr/bin/mount -o remount,bind,ro,nosuid,nodev "$ROOT/runtime"
/usr/bin/mount --bind "$CODE" "$ROOT/app/cognitum"
/usr/bin/mount -o remount,bind,ro,nosuid,nodev "$ROOT/app/cognitum"
# /dev and /proc are deliberately not mounted. No user home, /etc secrets,
# /mnt, system IPC, cloud keys or host network access is available here.
# Drop all capabilities AFTER chroot; prlimit bounds address space, CPU,
# descriptors and core dumps. This is a trusted-code research sandbox,
# NOT a claim of cgroup pids/memory or syscall filtering.
exec /usr/sbin/chroot "$ROOT" \
    /usr/bin/setpriv --no-new-privs --bounding-set=-all --inh-caps=-all --ambient-caps=-all \
    /usr/bin/prlimit --as=1073741824 --cpu=8 --nofile=128 --core=0 --fsize=8388608 -- \
    /runtime/bin/python3 -I /app/cognitum/sandbox_child.py
