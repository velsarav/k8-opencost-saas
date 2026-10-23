# OpenCost in Kubernetes: SaaSification of AI Services

This repository provides a deployable, three-team workload environment for
demonstrating OpenCost allocation. Each service is placed in its own namespace
and carries both Kubernetes application labels and ownership labels.

## Deploy

Install kube-prometheus-stack, then install OpenCost with the included
Prometheus endpoint and ServiceMonitor configuration:

```sh
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add opencost https://opencost.github.io/opencost-helm-chart
helm repo update
helm upgrade --install kube-prometheus-stack \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace
helm upgrade --install opencost opencost/opencost \
  --namespace opencost --create-namespace \
  --values helm/opencost-values.yaml

kubectl apply -f kubernetes/opencost-demo.yaml
kubectl apply -f kubernetes/load-generator.yaml
kubectl apply -f kubernetes/grafana-dashboards.yaml
kubectl apply -f kubernetes/ai-metrics-service.yaml
kubectl get deployments,pods -A -l app.kubernetes.io/part-of=opencost-ai-demo
```

The HorizontalPodAutoscalers require the Kubernetes Metrics Server. They can be
removed if the target cluster does not provide `metrics.k8s.io`.

## Allocation dimensions

- `customer-chat`: `customer-chat` namespace; `conversational-ai` team; three
  replicas requesting 500m CPU and 1Gi memory each.
- `document-ai`: `document-ai` namespace; `document-intelligence` team; two
  replicas requesting 1 CPU and 2Gi memory each.
- `vision-ai`: `vision-ai` namespace; `computer-vision` team; two replicas
  requesting 1500m CPU and 3Gi memory each.

Use the `team` or `opencost.io/team` label in OpenCost allocation queries to
group costs by owner. `app.kubernetes.io/part-of=opencost-ai-demo` selects all
demo resources.

## Load generation

`load-generator.yaml` creates a `load-testing` namespace and a continuously
running pod. It issues one request per second to each service via their
cluster-local DNS names:

- `customer-chat.customer-chat.svc.cluster.local`
- `vision-ai.vision-ai.svc.cluster.local`

## Grafana dashboards

`grafana-dashboards.yaml` provisions two dashboards as ConfigMaps in the
`monitoring` namespace:

- **AI Service Usage** compares observed CPU and memory consumption with the
  OpenCost request-allocation metrics.
- **AI Service Cost Allocation** estimates hourly and monthly CPU-plus-memory
  cost by service and pod using OpenCost allocation and node-price metrics.

The ConfigMaps use the `grafana_dashboard: "1"` label, which is recognized by
the Grafana sidecar used by common kube-prometheus-stack installations. If the
Grafana deployment watches another namespace or label, adjust the ConfigMap
namespace or label to its sidecar configuration.

## AI request metrics

The Dockerized Python service in `services/ai-metrics-service` produces
Prometheus metrics for request volume, tokens, and response latency. Build it
before applying its Kubernetes Deployment:

```sh
docker build -t ai-metrics-service:1.0.0 services/ai-metrics-service
```

For a remote cluster, push the image to a registry and replace
`ai-metrics-service:1.0.0` in `kubernetes/ai-metrics-service.yaml` with that
image reference. The deployment's Pod and Service carry Prometheus scrape
annotations.

Send a synthetic inference request after port-forwarding the Service:

```sh
kubectl -n ai-observability port-forward svc/ai-metrics-service 8080:8080
curl -X POST http://localhost:8080/infer \
  -H 'content-type: application/json' \
  -d '{"service":"customer-chat","model":"gpt-demo","input_tokens":240,"output_tokens":90,"processing_ms":120}'
```

The `/metrics` endpoint exposes `request_count_total`, `token_count_total`,
and the `response_latency_seconds` histogram.

## Local Verification & Web UIs

### Check What Is Running Locally

```sh
# Kind cluster and Kubernetes context
kind get clusters
kubectl config current-context
kubectl get nodes

# All pods or only the AI demo workloads
kubectl get pods -A
kubectl get deployments,pods,svc -A -l app.kubernetes.io/part-of=opencost-ai-demo

# Inspect individual platform namespaces
kubectl get pods,svc -n monitoring
kubectl get pods,svc -n ai-observability
kubectl get pods,svc -n opencost

# Installed Helm releases and active local port-forwards
helm list -A
lsof -iTCP -sTCP:LISTEN -P -n | grep -E ':(3000|8080|9090|9091|9003)'
```

### 1. `monitoring` (Grafana & Prometheus)

**Grafana:**

```sh
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
```

- **Grafana UI**: <http://localhost:3000>
- **Username**: `admin`
- **Password**:
  ```sh
  kubectl -n monitoring get secret kube-prometheus-stack-grafana -o jsonpath='{.data.admin-password}' | base64 --decode; echo
  ```
- Navigate to **Dashboards** → **AI Service Usage** and **AI Service Cost Allocation**.

**Prometheus (optional):**

```sh
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9091:9090
```

- **Prometheus UI**: <http://localhost:9091>

### 2. `ai-observability` (`ai-metrics-service`)

```sh
kubectl -n ai-observability port-forward svc/ai-metrics-service 8080:8080
```

- **Interactive Swagger UI**: <http://localhost:8080/docs>
- **Prometheus Metrics**: <http://localhost:8080/metrics>
- **Health Check**: <http://localhost:8080/healthz>

### 3. `opencost` (OpenCost UI & Cost API)

```sh
kubectl -n opencost port-forward svc/opencost 9090:9090 9003:9003
```

- **OpenCost Web UI**: <http://localhost:9090>
- **Allocation API (by namespace)**: <http://localhost:9003/allocation/compute?window=1d&aggregate=namespace>
- **Allocation API (by team label)**: <http://localhost:9003/allocation/compute?window=1d&aggregate=label:team>
- **OpenCost Prometheus Metrics**: <http://localhost:9003/metrics>
