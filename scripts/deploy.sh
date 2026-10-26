#!/bin/sh
# Deploy main to the live site (k3s on the server). Run on the server from ~/unmatched_matcher:
#   sh scripts/deploy.sh
# The site runs in k3s (see ~/Infra/k8s/apps/unmatched/unmatched.yaml), not Docker Compose:
# a second copy would write the same tournament data, so never `docker compose up` this app.
set -eu
cd "$(dirname "$0")/.."
INFRA_YAML="$HOME/Infra/k8s/apps/unmatched/unmatched.yaml"
TAG="unmatched:$(date +%Y-%m-%d-%H%M)"

git pull --ff-only
docker build -t "$TAG" -f dockerfile .
docker save "$TAG" | sudo k3s ctr images import -
sudo k3s kubectl -n apps set image deploy/unmatched unmatched="docker.io/library/$TAG"
sudo k3s kubectl -n apps rollout status deploy/unmatched --timeout=180s

# Keep the Infra manifest in step with what's running (commit it from ~/Infra afterwards)
if [ -f "$INFRA_YAML" ]; then
    sed -i "s|image: docker.io/library/unmatched:.*|image: docker.io/library/$TAG|" "$INFRA_YAML"
    echo "Updated $INFRA_YAML to $TAG; commit it in ~/Infra."
fi
echo "Deployed $TAG."
