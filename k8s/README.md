# Kubernetes manifests (NRP / Nautilus)

D6 deployment. Inference services run as Deployments behind Services; batch CV
inference and the irrigation forecast refresh run as Jobs/CronJobs.

> Confirm namespace, storage class (Ceph), and image registry with the mentor
> before applying. Never inline secrets — use K8s Secrets.

```bash
kubectl apply -f k8s/irrigation/        # deploy irrigation inference service
kubectl get pods -n <namespace>
```

| Path | Resource |
|------|----------|
| `irrigation/` | Deployment + Service for the irrigation API |
| `cv/` | Batch Job for inference on new orthomosaics (GPU) |
| `harvest/` | Deployment + Service for the harvest API |
| `base/` | Shared ConfigMap + CephFS PVCs |

Datasets live in **NRP S3** (`s3-west.nrp-nautilus.io`, pulled via DVC); the
CephFS PVCs in `base/pvc.yaml` hold model checkpoints and intermediates that
need a POSIX filesystem. S3 keys, MLflow URI, and API tokens come from a K8s
Secret (never the ConfigMap). See [Infrastructure](../docs/infrastructure.md).
