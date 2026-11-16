#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Development image entrypoint. Applies the optional extra certificate, then
# replaces this shell with the container command.
set -eu
_dev_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# shellcheck disable=SC1091
. "$_dev_dir/dev-ca-env.sh"
unset _dev_dir _DEV_CA_STATUS
exec "$@"
