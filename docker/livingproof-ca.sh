# SPDX-License-Identifier: Apache-2.0
# Login shells in the development image load the optional extra certificate.
. /usr/local/bin/dev-ca-env.sh
unset _DEV_CA_STATUS
