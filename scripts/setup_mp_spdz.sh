#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 /path/to/MP-SPDZ" >&2
    exit 2
fi

target=$1
revision=9d809599ea6ce627216a389ca7d984fbb75d0cb9

if [[ ! -d "$target/.git" ]]; then
    git clone https://github.com/data61/MP-SPDZ.git "$target"
fi

git -C "$target" fetch --depth 1 origin "$revision"
git -C "$target" checkout --detach "$revision"
make -C "$target" -j"$(getconf _NPROCESSORS_ONLN)" \
    CXX="${CXX:-g++}" semi-party.x shamir-party.x

echo "MP-SPDZ $revision is ready at $target"
