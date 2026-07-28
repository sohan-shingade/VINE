# Kubernetes manifests (NRP / Nautilus)

D6 inference runs as a Deployment behind an internal `ClusterIP` Service. Batch
vision inference belongs in a Job/CronJob; sensor ingestion and irrigation data
refresh belong in CronJobs.

The checked-in irrigation manifest is deliberately not directly deployable: its
`IMAGE_TAG` token must be replaced with the immutable Git commit SHA built by CI.
The registry path follows the confirmed NRP GitLab registry/group pattern:
`gitlab-registry.nrp-nautilus.io/ihv/vine/irrigation:<commit-sha>`.

## Build and smoke-test locally

From the repository root:

```bash
docker build --pull \
  -f docker/d2_irrigation.Dockerfile \
  -t vine-d2-irrigation:local \
  .

docker run --rm -d \
  --name vine-irrigation \
  -p 8000:8000 \
  -e VINE_DATA_DIR=/app/data \
  -v "$PWD/data:/app/data:ro" \
  vine-d2-irrigation:local

docker exec vine-irrigation python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz').read().decode())"
docker stop vine-irrigation
```

The build context excludes `.env`, `.dvc`, data, models, and other generated or
machine-local content through `.dockerignore`.

## Render and validate without deploying

First confirm the namespace, PVC/storage class, registry pull-secret convention,
and GPU reservation process with the mentor. `vine-data` is expected to contain
sensor snapshots at `raw/sensors/*.parquet`; the API mounts it read-only. This
CPU-only persistence service requests no GPU.

```bash
export NAMESPACE='<mentor-confirmed-namespace>'
export IMAGE_TAG='<full-git-commit-sha>'
export IMAGE="gitlab-registry.nrp-nautilus.io/ihv/vine/irrigation:${IMAGE_TAG}"

kubectl set image \
  -f k8s/d6_serving/irrigation-deployment.yaml \
  api="$IMAGE" \
  --local -o yaml > irrigation-deployment.rendered.yaml

kubectl apply --dry-run=client -n "$NAMESPACE" \
  -f k8s/base/configmap.yaml \
  -f irrigation-deployment.rendered.yaml \
  -f k8s/d6_serving/irrigation-service.yaml
```

The PVC manifest uses the current project convention (`rook-cephfs`), but that
cluster-specific choice still requires mentor confirmation. Render or inspect it
separately before provisioning storage:

```bash
kubectl apply --dry-run=client -n "$NAMESPACE" -f k8s/base/pvc.yaml
```

## Apply only after explicit approval

After the image exists and the cluster-specific values above are confirmed:

```bash
kubectl apply -n "$NAMESPACE" \
  -f k8s/base/configmap.yaml \
  -f k8s/base/pvc.yaml \
  -f irrigation-deployment.rendered.yaml \
  -f k8s/d6_serving/irrigation-service.yaml
```

Do not store credentials in these manifests or in the ConfigMap. S3 keys,
InfluxDB tokens, and MLflow URIs must come from Kubernetes Secrets when a
workload needs them. The current snapshot-only irrigation API needs none of
those credentials.

| Path | Resource |
|------|----------|
| `d1_ingest/` | Sensor refresh CronJob |
| `d6_serving/irrigation-deployment.yaml` | CPU-only irrigation API Deployment |
| `d6_serving/irrigation-service.yaml` | Internal irrigation `ClusterIP` Service |
| `d6_serving/vision-batch-job.yaml` | Batch vision inference template |
| `base/` | Shared non-secret ConfigMap and PVC templates |

Datasets live in NRP S3 (`s3-west.nrp-nautilus.io`; in-cluster endpoint
`http://rook-ceph-rgw-nautiluss3.rook`). CephFS is intended for large files and
checkpoints; small-file RBD and exact storage classes must be confirmed before
cluster use.
