# Kubernetes deployment notes
1. Build and push API image to ECR, then replace the image in `api-deployment.yaml`.
2. Create namespace: `kubectl apply -f namespace.yaml`.
3. Create secret out-of-band (never commit real credentials): `kubectl -n fleettrack create secret generic fleettrack-secrets --from-literal=database-url='postgresql+psycopg://USER:PASS@HOST:5432/DB'`.
4. Deploy: `kubectl apply -f api-deployment.yaml`.
5. Check: `kubectl -n fleettrack get pods,svc` and `kubectl -n fleettrack logs deploy/fleettrack-api`.

This manifest assumes managed PostgreSQL and a separately deployed secured MQTT broker. Do not use an in-cluster public database for production. Add TLS ingress, NetworkPolicies, PodDisruptionBudget, autoscaling, secrets manager integration, and image scanning before production.
