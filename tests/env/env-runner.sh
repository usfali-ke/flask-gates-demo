#!/usr/bin/env bash
# Registers and runs the environment test runner for one job
# (README: "Environment test runner"). Every test after a deploy is its own
# job, so keep it in a loop while a release runs:
#
#     while :; do GH_TOKEN=... bash tests/env/env-runner.sh [runner dir]; done
#
# Loops with different runner dirs run side by side (each registers under
# its own name; tests/env/env-up.sh gives every job its own ports).
#
# The runner dir holds an unpacked actions/runner release (default
# ~/actions-runner-env). The runner runs as the env-tester ServiceAccount,
# with a 2-hour token in a kubeconfig only this user can read; GH_TOKEN
# (repo admin) is used for the registration token and not passed on.
#
# Prerequisite, mirroring django-gates-demo: the tool namespace below must
# hold the env-tester ServiceAccount and a Role/RoleBinding that lets it
# list pods and port-forward in each environment namespace
# (flask-gates-demo-dev|-stg|-prod). The namespace does not exist yet:
#
#     kubectl create namespace flask-gates-demo-tools
#     kubectl -n flask-gates-demo-tools create serviceaccount env-tester
#     for ns in flask-gates-demo-dev flask-gates-demo-stg flask-gates-demo-prod; do
#       kubectl -n "$ns" create role env-tester --verb=get,list,watch,create --resource=pods,pods/portforward,services
#       kubectl -n "$ns" create rolebinding env-tester --role=env-tester --serviceaccount=flask-gates-demo-tools:env-tester
#     done
set -euo pipefail

repo=usfali-ke/flask-gates-demo
label=flask-gates-demo-env
tools_ns=flask-gates-demo-tools
dir=${1:-$HOME/actions-runner-env}
kubeconfig=$HOME/.kube/env-tester.json

[ -x "$dir/config.sh" ] || { echo "no actions runner in $dir" >&2; exit 1; }

mkdir -p "$(dirname "$kubeconfig")"
token=$(kubectl -n "$tools_ns" create token env-tester --duration=2h)
# umask in a subshell only: the runner's checkouts must stay readable by
# the tool containers (cap-drop ALL: root there can't override modes).
(umask 077; kubectl config view --minify --raw -o json \
  | jq --arg t "$token" --arg ns "$tools_ns" \
      '.users[0].user = {token: $t} | .contexts[0].context.namespace = $ns' \
  > "$kubeconfig")
unset token

registration=$(curl -fsS -X POST -H "Authorization: Bearer ${GH_TOKEN:?GH_TOKEN is not set}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${repo}/actions/runners/registration-token" | jq -r .token)

cd "$dir"
./config.sh --unattended --replace --ephemeral --url "https://github.com/${repo}" \
  --name "env-$(hostname -s)-$(basename "$dir")" --labels "$label" --token "$registration"
unset registration
# Node tries each address of a host for only 250 ms by default (happy
# eyeballs). With DNS handing out an unroutable NAT64 address, the IPv6
# attempts time out and the artifact upload fails with ETIMEDOUT, even at
# 2 s per address under load: IPv4 first, no racing.
exec env -u GH_TOKEN KUBECONFIG="$kubeconfig" NODE_OPTIONS="--dns-result-order=ipv4first --no-network-family-autoselection" ./run.sh
