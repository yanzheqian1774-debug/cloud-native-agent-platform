#!/bin/sh
set -eu

SCENARIO_ID='s5-v0.2-supplier-quality-v1'
NAMESPACE='s5-v02-supplier-quality-demo'
scenario=''
namespace=''
target_dir=''
confirmation=''

fail() {
  echo "reset: $1" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --scenario) [ "$#" -ge 2 ] || fail 'missing scenario value'; scenario=$2; shift 2 ;;
    --namespace) [ "$#" -ge 2 ] || fail 'missing namespace value'; namespace=$2; shift 2 ;;
    --target-dir) [ "$#" -ge 2 ] || fail 'missing target directory'; target_dir=$2; shift 2 ;;
    --confirm) [ "$#" -ge 2 ] || fail 'missing confirmation value'; confirmation=$2; shift 2 ;;
    *) fail 'unknown or implicit argument' ;;
  esac
done

[ "$scenario" = "$SCENARIO_ID" ] || fail 'exact scenario is required'
[ "$namespace" = "$NAMESPACE" ] || fail 'exact namespace is required'
[ "$confirmation" = "$SCENARIO_ID@$NAMESPACE" ] || fail 'exact confirmation is required'
[ -n "$target_dir" ] || fail 'explicit target directory is required'
case "$target_dir" in /*) ;; *) fail 'target directory must be absolute' ;; esac
[ "$target_dir" != '/' ] || fail 'root target is prohibited'
case "$target_dir" in *'*'*|*'?'*|*'['*|*']'*) fail 'wildcard-like target is prohibited' ;; esac
[ "$(basename -- "$target_dir")" = "$NAMESPACE" ] || fail 'target must end in exact namespace'

[ -e "$target_dir" ] || { echo "already reset $SCENARIO_ID at $target_dir"; exit 0; }
[ -d "$target_dir" ] || fail 'target is not a directory'
marker="$target_dir/.scenario-pack-scope"
[ -f "$marker" ] || fail 'unmarked target refused'
[ "$(sed -n '1p' "$marker")" = "scenario=$SCENARIO_ID" ] || fail 'foreign scenario marker refused'
[ "$(sed -n '2p' "$marker")" = "namespace=$NAMESPACE" ] || fail 'foreign namespace marker refused'

rm -rf -- "$target_dir"
echo "reset $SCENARIO_ID at $target_dir"
