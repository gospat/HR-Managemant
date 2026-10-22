#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
setup_dir="$PWD/.university-setup"
export UV_CACHE_DIR="$setup_dir/uv-cache"
export UV_LINK_MODE=copy
mkdir -p "$setup_dir"
# On normal developer machines, install default-libmysqlclient-dev using the
# system package manager. The cloud fallback below keeps the system read-only
# and uses signed Debian repository metadata and its verified package hashes.
if ! pkg-config --exists mysqlclient && ! pkg-config --exists mariadb; then
  mkdir -p "$setup_dir/apt/lists/partial" "$setup_dir/apt/archives/partial" "$setup_dir/apt/packages"
  printf '%s\n' 'deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main' > "$setup_dir/apt/sources.list"
  apt_options=(-o "Dir::Etc::sourcelist=$setup_dir/apt/sources.list" -o Dir::Etc::sourceparts=- -o "Dir::State::lists=$setup_dir/apt/lists" -o "Dir::Cache::archives=$setup_dir/apt/archives")
  apt-get "${apt_options[@]}" update
  (cd "$setup_dir/apt/packages" && apt-get "${apt_options[@]}" download libmariadb-dev libmariadb-dev-compat)
  for package in "$setup_dir"/apt/packages/*.deb; do dpkg-deb -x "$package" "$setup_dir/sysroot"; done
  export MYSQLCLIENT_CFLAGS="-I$setup_dir/sysroot/usr/include/mariadb"
  export MYSQLCLIENT_LDFLAGS=-l:libmariadb.so.3
fi
export CC=gcc
uv venv --allow-existing .venv
uv pip install --python .venv/bin/python --require-hashes -r requirements-university.lock
npm --prefix frontend ci --cache "$setup_dir/npm-cache" --no-audit --no-fund
python scripts/university_dev.py init
npm --prefix frontend run build
npm --prefix frontend run typecheck
