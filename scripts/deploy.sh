#!/usr/bin/env bash
# Deploy GitHub main of unmatched_matcher to the live site (unmatched.machaka.net: k3s, the pod runs on the Acer).
# Run on the PC, in Git Bash (not PowerShell's `bash`, which is WSL: no ssh keys, kubeconfig or GitHub login there):
#   bash scripts/deploy.sh            # deploy
#   bash scripts/deploy.sh --dry-run  # print every step; only reads this PC's clones and GitHub, changes nothing
#
# 1. The server pulls main and builds the image (tag = build time).
# 2. The image goes server -> this PC -> Acer and is loaded into k3s there: the pod never pulls (imagePullPolicy:
#    Never, strategy Recreate), so an image missing on the Acer leaves the site down. The PC has keyed ssh and
#    passwordless sudo on the Acer; the server has no key for it (like Infra's lab/build.sh). Nothing asks a password.
# 3. The tag goes into the PC's Infra clone, k8s/apps/unmatched/unmatched.yaml (both the `stats` init step and the
#    app), committed alone as "unmatched: deploy <tag>" and pushed to main. Flux applies k8s/ from main every
#    10 minutes and puts back whatever main says, so the push is what makes the deploy stay.
# 4. The file is applied right away, Flux is asked to fetch main now, then the rollout, the images, the site and
#    Flux's applied commit are checked.
#
# The site runs in k3s, not Docker Compose: a second copy would write the same tournament data, so never
# `docker compose up` this app.
set -euo pipefail

SERVER=moudimash99@192.168.1.116
ACER=moudimash99@192.168.1.93      # unmatched.yaml's nodeSelector is acer-laptop
SSH="ssh -o BatchMode=yes -o ConnectTimeout=10"   # a missing key fails instead of asking a password
KUBE="kubectl --context homelab"
REPO=$(cd "$(dirname "$0")/.." && pwd)
INFRA=${INFRA:-$(cd "$REPO/../Infra" 2>/dev/null && pwd || echo "$REPO/../Infra")}
MANIFEST=k8s/apps/unmatched/unmatched.yaml
SITE=https://unmatched.machaka.net/
TAG=$(date +%Y-%m-%d-%H%M)
IMAGE=docker.io/library/unmatched:$TAG
PATTERN='image: docker.io/library/unmatched:[A-Za-z0-9._-]*'

DRY=0
case "${1:-}" in
    --dry-run|-n) DRY=1 ;;
    "") ;;
    *) echo "usage: bash scripts/deploy.sh [--dry-run]" >&2; exit 2 ;;
esac

STEP="checks on the PC"
ON_FAIL=""
trap 'rc=$?; if [ "$rc" != 0 ]; then echo "deploy.sh: stopped during \"$STEP\". $ON_FAIL" >&2; fi' EXIT
die() { echo "deploy.sh: $*" >&2; exit 1; }
warn() { echo "  WARNING: $*"; }
say() { STEP=$1; printf '\n== %s\n' "$1"; }
# run CMD: print CMD, then run it unless --dry-run (a string, so pipes and remote quoting print as they run)
run() {
    printf '  $ %s\n' "$1"
    if [ "$DRY" = 0 ]; then eval "$1"; fi
}

if [ "$DRY" = 1 ]; then
    echo "DRY RUN: each step is printed, not run. Only read-only checks on this PC and GitHub run."
fi

say "0. Checks on the PC"
case "$(uname -r)" in *[Mm]icrosoft*) die "this is WSL: run it from Git Bash." ;; esac
for tool in git ssh kubectl curl sed diff; do
    command -v "$tool" >/dev/null || die "$tool not found."
done
kubectl config get-contexts homelab >/dev/null 2>&1 || die "no kubectl context 'homelab' on this PC."
[ -f "$INFRA/$MANIFEST" ] || die "no $INFRA/$MANIFEST (set INFRA=<path of the Infra clone>)."
[ "$(git -C "$INFRA" symbolic-ref --short HEAD)" = main ] || die "the Infra clone ($INFRA) is not on main."
git -C "$INFRA" diff --quiet HEAD -- "$MANIFEST" \
    || die "$MANIFEST has uncommitted changes in the Infra clone: commit or drop them first."

# The push must carry this deploy only: other commits on the PC's Infra main would go live with it.
infra_github=$(git -C "$INFRA" ls-remote origin refs/heads/main | cut -f1)
[ -n "$infra_github" ] || die "can't read Infra main on GitHub."
infra_head=$(git -C "$INFRA" rev-parse HEAD)
if [ "$infra_head" = "$infra_github" ]; then
    echo "  Infra clone: main = GitHub main (${infra_head:0:7})"
elif git -C "$INFRA" cat-file -e "$infra_github^{commit}" 2>/dev/null \
        && git -C "$INFRA" merge-base --is-ancestor "$infra_head" "$infra_github"; then
    echo "  Infra clone: behind GitHub main; step 3 fast-forwards it first"
elif git -C "$INFRA" cat-file -e "$infra_github^{commit}" 2>/dev/null; then
    die "the Infra clone's main has commits not on GitHub: pushing would put them live too. Push or sort them first."
elif [ "$DRY" = 1 ]; then
    echo "  Infra clone: GitHub main (${infra_github:0:7}) is newer than this clone; a real run fetches it here and stops if this clone has unpushed commits"
else
    git -C "$INFRA" fetch -q origin main
    [ "$(git -C "$INFRA" rev-list --count origin/main..HEAD)" = 0 ] \
        || die "the Infra clone's main has commits not on GitHub: pushing would put them live too. Push or sort them first."
    echo "  Infra clone: behind GitHub main; step 3 fast-forwards it first"
fi

old_lines=$(grep -c "$PATTERN" "$INFRA/$MANIFEST" || true)
[ "$old_lines" -ge 1 ] || die "no 'image: docker.io/library/unmatched:...' line in $MANIFEST."
grep -q "unmatched:$TAG\$" "$INFRA/$MANIFEST" && die "$MANIFEST already has the tag $TAG: wait a minute and run again."
echo "  manifest now: $(grep -o "$PATTERN" "$INFRA/$MANIFEST" | sed 's/^image: //' | sort | uniq -c | tr -s ' ' | sed 's/^ //' | paste -sd ',' -) ($old_lines lines)"

# What gets built is GitHub main, not this PC's working copy.
WANT=$(git -C "$REPO" ls-remote origin refs/heads/main | cut -f1)
[ -n "$WANT" ] || die "can't read unmatched_matcher main on GitHub."
echo "  deploying unmatched_matcher ${WANT:0:7} (GitHub main) as $IMAGE"
[ "$(git -C "$REPO" rev-parse HEAD)" = "$WANT" ] \
    || warn "this PC's clone is at $(git -C "$REPO" rev-parse --short HEAD), not GitHub main: its commits are not in this deploy (push them first if you meant them)."
[ -z "$(git -C "$REPO" status --porcelain)" ] || warn "this PC's clone has uncommitted changes: they are not in this deploy."

say "1. Build on the server (it pulls GitHub main)"
ON_FAIL="Nothing has changed on the site."
cmd="$SSH $SERVER 'cd ~/unmatched_matcher && git pull --ff-only -q && git rev-parse HEAD'"
printf '  $ %s\n' "$cmd"
if [ "$DRY" = 0 ]; then
    have=$(eval "$cmd")
    [ "$have" = "$WANT" ] || die "the server's clone is at $have, not GitHub main $WANT: sort it out there (local commits?) and run again."
fi
run "$SSH $SERVER 'cd ~/unmatched_matcher && docker build -t unmatched:$TAG -f dockerfile .'"

say "2. Load the image on the Acer (server -> this PC -> Acer, no password)"
run "$SSH $SERVER 'docker save unmatched:$TAG' | $SSH $ACER 'sudo -n k3s ctr -n k8s.io images import -'"
cmd="$SSH $ACER 'sudo -n k3s ctr -n k8s.io images ls -q' | grep -Fx $IMAGE"
printf '  $ %s\n' "$cmd"
if [ "$DRY" = 0 ]; then
    eval "$cmd" >/dev/null || die "$IMAGE is not in the Acer's k3s after the import: not deploying it."
    echo "  $IMAGE is on the Acer"
fi

say "3. Write the tag in the Infra clone, commit it alone, push main"
ON_FAIL="The image is on the Acer; the site still runs the old one."
sed_cmd="sed 's|$PATTERN|image: $IMAGE|' $MANIFEST"
run "git -C '$INFRA' pull --ff-only -q origin main"
if [ "$DRY" = 1 ]; then
    echo "  $ (cd '$INFRA' && $sed_cmd > tmp && cat tmp > $MANIFEST)   # the change it makes:"
    (cd "$INFRA" && eval "$sed_cmd" | diff -u --label "a/$MANIFEST" --label "b/$MANIFEST" "$MANIFEST" -) | sed 's/^/      /' || true
else
    [ "$(git -C "$INFRA" rev-list --count origin/main..HEAD)" = 0 ] \
        || die "the Infra clone's main has commits not on GitHub: not pushing them with this deploy."
    git -C "$INFRA" diff --quiet HEAD -- "$MANIFEST" || die "$MANIFEST changed in the Infra clone meanwhile."
    tmp=$(mktemp)
    printf '  $ (cd %s && %s > %s && cat %s > %s)\n' "'$INFRA'" "$sed_cmd" "$tmp" "$tmp" "$MANIFEST"
    (cd "$INFRA" && eval "$sed_cmd" > "$tmp" && cat "$tmp" > "$MANIFEST")
    rm -f "$tmp"
    # Exactly the image lines may change (a line-ending rewrite would change them all), and only to the new tag.
    numstat=$(git -C "$INFRA" -c core.safecrlf=false diff --numstat HEAD -- "$MANIFEST" | cut -f1,2)
    new_lines=$(grep -c "image: $IMAGE\$" "$INFRA/$MANIFEST" || true)
    if [ "$numstat" != "$old_lines"$'\t'"$old_lines" ] || [ "$new_lines" != "$old_lines" ]; then
        git -C "$INFRA" checkout -q -- "$MANIFEST"
        die "the manifest edit changed more than the $old_lines image lines (diff: '$numstat'); undone, nothing committed."
    fi
    git -C "$INFRA" -c core.safecrlf=false diff HEAD -- "$MANIFEST" | sed 's/^/      /'
fi
run "git -C '$INFRA' -c core.safecrlf=false commit -q -m 'unmatched: deploy $TAG' -m 'unmatched_matcher ${WANT:0:12} (GitHub main), built on the server and loaded on the Acer by unmatched_matcher/scripts/deploy.sh.' -- $MANIFEST"
ON_FAIL="The image is on the Acer and the tag is committed in the Infra clone but not on GitHub; the site still runs the old image. Pull (git pull --ff-only fails now: git pull --rebase, once the clone has no other changes) and push Infra main by hand."
flux_before=""
[ "$DRY" = 1 ] || flux_before=$($KUBE -n flux-system get kustomization apps -o jsonpath='{.status.lastAppliedRevision}' 2>/dev/null || true)
run "git -C '$INFRA' push -q origin main"
INFRA_COMMIT=$(git -C "$INFRA" rev-parse HEAD)
commit_label=${INFRA_COMMIT:0:7}
[ "$DRY" = 0 ] || commit_label="(the new commit)"

say "4. Apply now, ask Flux to fetch main, check the rollout"
ON_FAIL="The tag is on Infra main, so Flux applies it within 10 minutes anyway. Look at: $KUBE -n apps get pods -l app=unmatched; $KUBE -n apps describe deploy/unmatched."
run "(cd '$INFRA' && $KUBE apply -f $MANIFEST)"
run "$KUBE -n flux-system annotate --overwrite gitrepository/infra reconcile.fluxcd.io/requestedAt=$(date +%s)"
run "$KUBE -n apps rollout status deploy/unmatched --timeout=300s"

say "5. Check the images, the pod and the site"
echo "  $ $KUBE -n apps get deploy unmatched -o jsonpath='{.spec.template.spec.initContainers[*].image} {.spec.template.spec.containers[*].image}'   # all = $IMAGE"
echo "  $ $KUBE -n apps get pods -l app=unmatched   # one Running pod with $IMAGE"
echo "  $ curl -sS -o /dev/null -w '%{http_code}' --max-time 20 $SITE   # 200"
if [ "$DRY" = 0 ]; then
    images=$($KUBE -n apps get deploy unmatched \
        -o jsonpath='{.spec.template.spec.initContainers[*].image} {.spec.template.spec.containers[*].image}')
    for i in $images; do [ "$i" = "$IMAGE" ] || die "the Deployment has image $i, not $IMAGE."; done
    pods=$($KUBE -n apps get pods -l app=unmatched \
        -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.containerStatuses[0].image}{"\n"}{end}')
    echo "$pods" | sed 's/^/      /'
    echo "$pods" | grep -q " Running $IMAGE\$" || die "no Running pod with $IMAGE."
    code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "$SITE" || true)
    [ "$code" = 200 ] || die "$SITE answered $code, not 200."
    echo "  images, pod and site OK ($SITE: 200)"
fi

say "6. Wait until Flux has applied Infra $commit_label, so it stays (up to 4 minutes)"
echo "  $ $KUBE -n flux-system get kustomization apps -o jsonpath='{.status.lastAppliedRevision}'   # main@sha1:<this commit or newer>"
if [ "$DRY" = 0 ]; then
    applied=""
    for _ in $(seq 24); do
        rev=$($KUBE -n flux-system get kustomization apps -o jsonpath='{.status.lastAppliedRevision}' 2>/dev/null || true)
        sha=${rev##*:}
        if [ "$sha" = "$INFRA_COMMIT" ] || { [ "$rev" != "$flux_before" ] && [ -n "$sha" ] \
                && git -C "$INFRA" merge-base --is-ancestor "$INFRA_COMMIT" "$sha" 2>/dev/null; }; then
            applied=$rev; break
        fi
        sleep 10
    done
    if [ -n "$applied" ]; then
        echo "  Flux applied $applied: it will keep $IMAGE"
    else
        warn "Flux has not applied Infra ${INFRA_COMMIT:0:7} yet (it is at '${rev:-?}'). The tag is on main, so it will; see $KUBE -n flux-system get gitrepository,kustomization"
    fi
fi

if [ "$DRY" = 1 ]; then
    echo
    echo "Dry run done: nothing was built, loaded, committed, pushed or applied."
else
    echo
    echo "Deployed $IMAGE (unmatched_matcher ${WANT:0:7}, Infra ${INFRA_COMMIT:0:7})."
    echo "Still live later? $KUBE -n apps get deploy unmatched -o jsonpath='{.spec.template.spec.containers[0].image}'"
fi
