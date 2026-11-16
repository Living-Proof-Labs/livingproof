# SPDX-License-Identifier: Apache-2.0
# Optional extra certificate for the development image.
# Sourced by the entrypoint, login shells and postCreateCommand.
# Certificate variables are exported only when the extra file contains a PEM
# certificate. The bundle is a new mode-0600 file in a private directory, never
# a fixed path in /tmp. Empty proxy variables are removed. When a proxy is set,
# loopback names are added to NO_PROXY so local connections stay local.

_DEV_CA_STATUS=0
_dev_extra_ca=${DEV_EXTRA_CA:-/run/livingproof/extra-ca.crt}
_dev_system_ca=${DEV_SYSTEM_CA_BUNDLE:-/etc/ssl/certs/ca-certificates.crt}
_dev_umask=$(umask)
_dev_bundle=
_dev_list=
_dev_proxy_set=0

_dev_append() {
  [ -n "$1" ] || return 0
  case ",${_dev_list}," in
    *",${1},"*) ;;
    *)
      if [ -n "$_dev_list" ]; then
        _dev_list="${_dev_list},${1}"
      else
        _dev_list=$1
      fi
      ;;
  esac
}

for _dev_name in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy; do
  eval "_dev_value=\${$_dev_name-}"
  if [ -z "$_dev_value" ]; then
    unset "$_dev_name" || true
  else
    _dev_proxy_set=1
  fi
done

eval "_dev_no_proxy=\${NO_PROXY-}"
eval "_dev_no_proxy_lower=\${no_proxy-}"
if [ -z "$_dev_no_proxy" ]; then
  unset NO_PROXY || true
fi
if [ -z "$_dev_no_proxy_lower" ]; then
  unset no_proxy || true
fi

if [ "$_dev_proxy_set" -eq 1 ]; then
  _dev_old="${_dev_no_proxy},${_dev_no_proxy_lower}"
  _dev_rest=$_dev_old
  while [ -n "$_dev_rest" ]; do
    _dev_item=${_dev_rest%%,*}
    _dev_append "$_dev_item"
    case "$_dev_rest" in
      *,*) _dev_rest=${_dev_rest#*,} ;;
      *) _dev_rest= ;;
    esac
  done
  for _dev_host in localhost 127.0.0.1 ::1; do
    _dev_append "$_dev_host"
  done
  NO_PROXY=$_dev_list
  no_proxy=$_dev_list
  export NO_PROXY no_proxy
fi

if [ -f "$_dev_extra_ca" ] && grep -q "BEGIN CERTIFICATE" "$_dev_extra_ca"; then
  umask 077
  if [ -n "${DEV_COMBINED_CA_BUNDLE:-}" ] && [ ! -L "$DEV_COMBINED_CA_BUNDLE" ] \
      && [ ! -e "$DEV_COMBINED_CA_BUNDLE" ]; then
    if (set -C; : > "$DEV_COMBINED_CA_BUNDLE"); then
      _dev_bundle=$DEV_COMBINED_CA_BUNDLE
    fi
  fi
  if [ -z "$_dev_bundle" ]; then
    _dev_dir=
    if [ -n "${XDG_RUNTIME_DIR:-}" ]; then
      _dev_dir="${XDG_RUNTIME_DIR}/livingproof"
    elif [ -n "${HOME:-}" ]; then
      _dev_dir="${HOME}/.cache/livingproof"
    fi
    if [ -z "$_dev_dir" ] || [ -L "$_dev_dir" ] \
        || ! mkdir -p -m 700 "$_dev_dir" 2>/dev/null || [ ! -w "$_dev_dir" ]; then
      _dev_dir=$(mktemp -d "${TMPDIR:-/tmp}/livingproof-ca.XXXXXX")
    fi
    _dev_bundle=$(mktemp "${_dev_dir}/ca-bundle.XXXXXX")
  fi
  if cat "$_dev_system_ca" "$_dev_extra_ca" > "$_dev_bundle"; then
    export SSL_CERT_FILE="$_dev_bundle"
    export REQUESTS_CA_BUNDLE="$_dev_bundle"
    export CURL_CA_BUNDLE="$_dev_bundle"
    export PIP_CERT="$_dev_bundle"
    export GIT_SSL_CAINFO="$_dev_bundle"
    export UV_NATIVE_TLS=true
    export UV_SYSTEM_CERTS=true
  else
    if [ -n "$_dev_bundle" ] && [ ! -L "$_dev_bundle" ]; then
      rm -f "$_dev_bundle"
    fi
    echo "livingproof dev: cannot build a certificate bundle from ${_dev_system_ca}" >&2
    _DEV_CA_STATUS=1
  fi
  umask "$_dev_umask"
fi

unset -f _dev_append
unset _dev_extra_ca _dev_system_ca _dev_umask _dev_bundle _dev_list _dev_proxy_set \
  _dev_name _dev_value _dev_no_proxy _dev_no_proxy_lower _dev_old _dev_rest _dev_item \
  _dev_host _dev_dir
if [ "$_DEV_CA_STATUS" -ne 0 ]; then
  return "$_DEV_CA_STATUS"
fi
unset _DEV_CA_STATUS
