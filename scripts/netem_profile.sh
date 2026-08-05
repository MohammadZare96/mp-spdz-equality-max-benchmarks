#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 apply LAN|WAN [interface] | clear [interface]" >&2
    exit 2
}

action=${1:-}
profile=${2:-}

if [[ "$action" == "clear" ]]; then
    interface=${2:-lo}
    tc qdisc del dev "$interface" root 2>/dev/null || true
    exit 0
fi

[[ "$action" == "apply" ]] || usage
interface=${3:-lo}
case "$profile" in
    LAN) delay=1ms; rate=1000mbit ;;
    WAN) delay=50ms; rate=100mbit ;;
    *) usage ;;
esac

if ! tc qdisc show dev "$interface" >/dev/null 2>&1; then
    echo "tc requires CAP_NET_ADMIN (or sudo) for interface $interface" >&2
    exit 1
fi
tc qdisc replace dev "$interface" root netem delay "$delay" rate "$rate"
echo "$profile applied to $interface: delay=$delay rate=$rate"
