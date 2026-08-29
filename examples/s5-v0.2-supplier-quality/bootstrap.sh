#!/bin/sh
set -eu

SCENARIO_ID='s5-v0.2-supplier-quality-v1'
NAMESPACE='s5-v02-supplier-quality-demo'
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
scenario=''
namespace=''
target_dir=''

fail() {
  echo "bootstrap: $1" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --scenario) [ "$#" -ge 2 ] || fail 'missing scenario value'; scenario=$2; shift 2 ;;
    --namespace) [ "$#" -ge 2 ] || fail 'missing namespace value'; namespace=$2; shift 2 ;;
    --target-dir) [ "$#" -ge 2 ] || fail 'missing target directory'; target_dir=$2; shift 2 ;;
    *) fail 'unknown or implicit argument' ;;
  esac
done

[ "$scenario" = "$SCENARIO_ID" ] || fail 'exact scenario is required'
[ "$namespace" = "$NAMESPACE" ] || fail 'exact namespace is required'
[ -n "$target_dir" ] || fail 'explicit target directory is required'
case "$target_dir" in /*) ;; *) fail 'target directory must be absolute' ;; esac
[ "$target_dir" != '/' ] || fail 'root target is prohibited'
case "$target_dir" in *'*'*|*'?'*|*'['*|*']'*) fail 'wildcard-like target is prohibited' ;; esac
[ "$(basename -- "$target_dir")" = "$NAMESPACE" ] || fail 'target must end in exact namespace'

(cd "$script_dir" && sha256sum -c checksums.sha256 >/dev/null) || fail 'checksum verification failed'

marker="$target_dir/.scenario-pack-scope"
if [ -e "$target_dir" ]; then
  [ -d "$target_dir" ] || fail 'target exists and is not a directory'
  [ -f "$marker" ] || { [ -z "$(ls -A "$target_dir")" ] || fail 'unmarked non-empty target refused'; }
  if [ -f "$marker" ]; then
    [ "$(sed -n '1p' "$marker")" = "scenario=$SCENARIO_ID" ] || fail 'foreign scenario marker refused'
    [ "$(sed -n '2p' "$marker")" = "namespace=$NAMESPACE" ] || fail 'foreign namespace marker refused'
    rm -rf -- "$target_dir"
  fi
fi

mkdir -p "$target_dir/data" "$target_dir/catalog" "$target_dir/history" "$target_dir/knowledge"
cp "$script_dir/scenario-pack-v1.json" "$target_dir/"
cp "$script_dir/namespace.yaml" "$target_dir/"
cp "$script_dir/checksums.sha256" "$target_dir/"
cp "$script_dir/data/supplier-quality-cases-v1.json" "$target_dir/data/"
cp "$script_dir/catalog/descriptors-v1.json" "$target_dir/catalog/"
cp "$script_dir/catalog/published-roles-v1.json" "$target_dir/catalog/"
cp "$script_dir/history/synthetic-history-v1.json" "$target_dir/history/"
cp "$script_dir/knowledge/knowledge-pack-v1.json" "$target_dir/knowledge/"
cp "$script_dir/knowledge/8d-procedure-v1.md" "$target_dir/knowledge/"
{
  echo "scenario=$SCENARIO_ID"
  echo "namespace=$NAMESPACE"
} > "$marker"

echo "bootstrapped $SCENARIO_ID in $target_dir"
