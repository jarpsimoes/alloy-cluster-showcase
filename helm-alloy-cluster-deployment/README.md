# Grafana Alloy Cluster Deployment

This folder contains two independent Grafana Alloy deployment modes for monitoring
applications across Kubernetes namespaces. Deploy one at a time to compare behaviour
and gather evidence before choosing the mode for production.

## Folder structure

```
helm-alloy-cluster-deployment/
├── helmfile.yaml.gotmpl   # Helmfile with statefulset and daemonset environments
├── statefulset/
│   └── values.yaml        # StatefulSet: 3 clustered replicas, K8s-API logs
└── daemonset/
    └── values.yaml        # DaemonSet: one pod per node, file-based logs
```

## Signal comparison

| Signal  | StatefulSet                                   | DaemonSet                                    |
|---------|-----------------------------------------------|----------------------------------------------|
| Metrics | Sharded across replicas via cluster mode      | Filtered to node-local pods only             |
| Logs    | `loki.source.kubernetes` (K8s API streaming)  | `loki.source.file` (reads `/var/log/pods`)   |
| Traces  | OTLP receiver (apps push to service)          | OTLP receiver (apps push to node's pod)      |

## Prerequisites

### 1. Tools

```bash
# Helm
brew install helm

# Helmfile
brew install helmfile

# Helm diff plugin (required by helmfile)
helm plugin install https://github.com/databus23/helm-diff
```

### 2. Add the Grafana Helm repository

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

### 3. Create the monitoring namespace

```bash
kubectl create namespace monitoring
```

---

## Deploy: StatefulSet mode

### What it does

- Runs **3 clustered replicas** as a StatefulSet
- Metrics scraping is **sharded** across replicas — each target is scraped by exactly one pod
- Logs are collected via the **Kubernetes API** (`loki.source.kubernetes`) — no `/var/log/pods` hostPath mount required
- Traces are received over **OTLP gRPC (4317) and HTTP (4318)** and forwarded to Tempo
- Each pod has a **5Gi WAL PVC** — data survives pod restarts
- PodDisruptionBudget keeps at least **2 replicas available** during upgrades

### 1. Create the secret

```bash
kubectl create secret generic alloy-statefulset-secrets -n monitoring \
  --from-literal=prometheus_remote_write_url="https://$METRICS_HOST/api/v1/push" \
  --from-literal=prometheus_username="$METRICS_USERNAME" \
  --from-literal=prometheus_password="$TOKEN" \
  --from-literal=loki_push_url="https://$LOGS_HOST/loki/api/v1/push" \
  --from-literal=loki_username="$LOGS_USERNAME" \
  --from-literal=loki_password="$TOKEN" \
  --from-literal=tempo_endpoint="https://$TRACES_HOST/otlp" \
  --from-literal=tempo_username="$TRACES_USERNAME" \
  --from-literal=tempo_password="$TOKEN"
```

### 2. Preview the rendered manifests (dry-run)

```bash
cd helm-alloy-cluster-deployment
helmfile -e statefulset diff
```

### 3. Deploy

```bash
helmfile -e statefulset apply
```

### 4. Verify

```bash
# All 3 pods should be Running
kubectl get pods -n monitoring -l app.kubernetes.io/name=alloy

# Check Alloy is running and cluster peers are discovered
kubectl logs -n monitoring -l app.kubernetes.io/name=alloy --tail=50

# Check WAL PVCs were created
kubectl get pvc -n monitoring

# Access the Alloy UI (port-forward to any one replica)
kubectl port-forward -n monitoring statefulset/alloy-statefulset 12345:12345
# Open http://localhost:12345
```

### 5. Annotate your app pods for metric scraping

Add these annotations to any pod you want scraped:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"       # optional, defaults to the pod's port
  prometheus.io/path: "/metrics"   # optional, defaults to /metrics
```

### 6. Tear down

```bash
helmfile -e statefulset destroy

# Also remove the PVCs if you want a clean slate
kubectl delete pvc -n monitoring -l app.kubernetes.io/name=alloy
```

---

## Deploy: DaemonSet mode

### What it does

- Runs **one pod per node** — automatically scales with the cluster
- Metrics scraping is **node-local** — each pod only scrapes pods running on its own node
- Logs are collected by **tailing `/var/log/pods`** on each node directly
- Traces are received over **OTLP gRPC (4317) and HTTP (4318)** on the node's pod — apps should point to the node's IP or use `hostNetwork`
- Tolerates all taints so it runs on **every node** including control-plane nodes
- Runs as **privileged** with `runAsUser: 0` to read node log files

### 1. Create the secret

```bash
kubectl create secret generic alloy-daemonset-secrets -n monitoring \
  --from-literal=prometheus_remote_write_url="https://$METRICS_HOST/api/v1/push" \
  --from-literal=prometheus_username="$METRICS_USERNAME" \
  --from-literal=prometheus_password="$TOKEN" \
  --from-literal=loki_push_url="https://$LOGS_HOST/loki/api/v1/push" \
  --from-literal=loki_username="$LOGS_USERNAME" \
  --from-literal=loki_password="$TOKEN" \
  --from-literal=tempo_endpoint="https://$TRACES_HOST/otlp" \
  --from-literal=tempo_username="$TRACES_USERNAME" \
  --from-literal=tempo_password="$TOKEN"
```

### 2. Preview the rendered manifests (dry-run)

```bash
cd helm-alloy-cluster-deployment
helmfile -e daemonset diff
```

### 3. Deploy

```bash
helmfile -e daemonset apply
```

### 4. Verify

```bash
# One pod per node should be Running
kubectl get pods -n monitoring -l app.kubernetes.io/name=alloy -o wide

# Check logs on a specific node's pod
kubectl logs -n monitoring <pod-name> --tail=50

# Access the Alloy UI on any pod
kubectl port-forward -n monitoring <pod-name> 12345:12345
# Open http://localhost:12345
```

### 5. Annotate your app pods for metric scraping

Same annotations as StatefulSet mode:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8080"
  prometheus.io/path: "/metrics"
```

### 6. Tear down

```bash
helmfile -e daemonset destroy
```

---

## Switch between modes

Both releases are isolated — they use different Helm release names and different secrets,
so you can switch cleanly without any overlap.

```bash
# Remove StatefulSet, deploy DaemonSet
helmfile -e statefulset destroy
helmfile -e daemonset apply

# Remove DaemonSet, go back to StatefulSet
helmfile -e daemonset destroy
helmfile -e statefulset apply
```

## Customising backends

Edit the relevant `values.yaml` and update the secret. The config map is rendered
from the inline `alloy.configMap.content` field, so all Alloy pipeline changes are
made there.

To update after a change:

```bash
helmfile -e statefulset apply   # or daemonset
```
