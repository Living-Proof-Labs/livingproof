# SPDX-License-Identifier: Apache-2.0
# Optional extra certificate for the development image.
# Sourced by the entrypoint, login shells and postCreateCommand.
# Certificate variables are exported only when the extra file contains a PEM
# certificate. Empty proxy variables are removed so an unset host value cannot
# change uv, pip or curl.

_DEV_CA_STATUS=0
_dev_extra_ca=${DEV_EXTRA_CA:-/etc/ssl/certs/extra-ca.crt}
_dev_system_ca=${DEV_SYSTEM_CA_BUNDLE:-/etc/ssl/certs/ca-certificates.crt}
_dev_bundle=${DEV_COMBINED_CA_BUNDLE:-/tmp/livingproof-ca-bundle.crt}

for _dev_name in HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy; do
  eval "_dev_value=\${$_dev_name-}"
  if [ -z "$_dev_value" ]; then
    unset "$_dev_name" || true
  fi
done

if [ -f "$_dev_extra_ca" ] && grep -q "BEGIN CERTIFICATE" "$_dev_extra_ca"; then
  if cat "$_dev_system_ca" "$_dev_extra_ca" > "$_dev_bundle"; then
    chmod 644 "$_dev_bundle" 2>/dev/null || true
    export SSL_CERT_FILE="$_dev_bundle"
    export REQUESTS_CA_BUNDLE="$_dev_bundle"
    export CURL_CA_BUNDLE="$_dev_bundle"
    export PIP_CERT="$_dev_bundle"
    export UV_NATIVE_TLS=true
    export UV_SYSTEM_CERTS=true
  else
    rm -f "$_dev_bundle"
    echo "livingproof dev: cannot build a certificate bundle from ${_dev_system_ca}" >&2
    _DEV_CA_STATUS=1
  fi
fi

unset _dev_extra_ca _dev_system_ca _dev_bundle _dev_name _dev_value
if [ "$_DEV_CA_STATUS" -ne 0 ]; then
  return "$_DEV_CA_STATUS"
fi
unset _DEV_CA_STATUS
