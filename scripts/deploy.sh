#!/bin/sh
# Deploy main to the live site (k3s; the pod runs on the Acer, 192.168.1.93, since 2026-11-02). Run on the server
# from ~/unmatched_matcher, in a terminal (it asks for the Acer's SSH and sudo passwords):
#   sh scripts/deploy.sh
# The image is built on the server and loaded on the Acer: the pod never pulls (imagePullPolicy: Never), so an image
# only on the server leaves the site down (Recreate stops the old copy first).
# The site runs in k3s (see ~/Infra/k8s/apps/unmatched/unmatched.yaml), not Docker Compose:
# a second copy would write the same tournament data, so never `docker compose up` this app.
set -eu
cd "$(dirname "$0")/.."
INFRA_YAML="$HOME/Infra/k8s/apps/unmatched/unmatched.yaml"
TAG="unmatched:$(date +%Y-%m-%d-%H%M)"

git pull --ff-only
docker build -t "$TAG" -f dockerfile .
NODE=192.168.1.93   # the Acer: unmatched.yaml's nodeSelector is acer-laptop
docker save "$TAG" -o /tmp/unmatched-image.tar
scp /tmp/unmatched-image.tar "$NODE:/tmp/"
ssh -t "$NODE" "sudo k3s ctr images import /tmp/unmatched-image.tar && rm /tmp/unmatched-image.tar"
rm /tmp/unmatched-image.tar
sudo k3s kubectl -n apps set image deploy/unmatched unmatched="docker.io/library/$TAG"
sudo k3s kubectl -n apps rollout status deploy/unmatched --timeout=180s

# Keep the Infra manifest in step with what's running (commit it from ~/Infra afterwards)
if [ -f "$INFRA_YAML" ]; then
    sed -i "s|image: docker.io/library/unmatched:.*|image: docker.io/library/$TAG|" "$INFRA_YAML"
    echo "Updated $INFRA_YAML to $TAG; commit it in ~/Infra."
fi
echo "Deployed $TAG."
