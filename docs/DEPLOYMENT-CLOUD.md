# Deploying with Docker on AWS, GCP, or Azure

This project ships with a production-ready Dockerfile. The steps below show how to build, push, and deploy the container to popular managed platforms.

## Prereqs
- Docker installed locally
- Access to a cloud account (AWS, GCP, or Azure)
- A container registry in that cloud
- Required env vars configured for your app (for example: PORT, database URLs, Redis, etc.)

## Build the image (local)
From the repo root:

```bash
docker build -t comex-stat-api:latest .
```

By default the app listens on port 3000. Adjust your cloud service port settings if your app uses a different port.

## AWS: ECR + ECS Fargate (recommended)
1) Create an ECR repo. This project uses `sri/comexstat`.
2) Authenticate Docker to ECR:

```bash
aws ecr get-login-password --region <REGION> | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.<REGION>.amazonaws.com
```

3) Tag and push:

```bash
docker tag comex-stat-api:latest 194133064894.dkr.ecr.us-east-2.amazonaws.com/sri/comexstat:latest
docker push 194133064894.dkr.ecr.us-east-2.amazonaws.com/sri/comexstat:latest
```

4) Create an ECS cluster (Fargate) and a task definition:
- Container port: 3000
- CPU/Memory: choose per load
- Env vars: set required values
- Logging: enable CloudWatch logs

5) Create a service from the task definition and expose it via an Application Load Balancer.

## GCP: Artifact Registry + Cloud Run
1) Create an Artifact Registry repo (Docker format).
2) Authenticate Docker:

```bash
gcloud auth configure-docker <REGION>-docker.pkg.dev
```

3) Tag and push:

```bash
docker tag comex-stat-api:latest <REGION>-docker.pkg.dev/<PROJECT_ID>/<REPO>/comex-stat-api:latest
docker push <REGION>-docker.pkg.dev/<PROJECT_ID>/<REPO>/comex-stat-api:latest
```

4) Deploy to Cloud Run:

```bash
gcloud run deploy comex-stat-api \
  --image <REGION>-docker.pkg.dev/<PROJECT_ID>/<REPO>/comex-stat-api:latest \
  --region <REGION> \
  --platform managed \
  --port 3000
```

Set env vars during deploy with `--set-env-vars` or in the Cloud Run console.

## Azure: ACR + Azure Container Apps
1) Create an Azure Container Registry (ACR) named `comexstatacr` (or similar).
2) Authenticate Docker to ACR:

```bash
az acr login --name <ACR_NAME>
```

3) Tag and push:

```bash
docker tag comex-stat-api:latest <ACR_NAME>.azurecr.io/comex-stat-api:latest
docker push <ACR_NAME>.azurecr.io/comex-stat-api:latest
```

4) Create a Container Apps environment and deploy:

```bash
az containerapp create \
  --name comex-stat-api \
  --resource-group <RESOURCE_GROUP> \
  --environment <CONTAINERAPPS_ENV> \
  --image <ACR_NAME>.azurecr.io/comex-stat-api:latest \
  --target-port 3000 \
  --ingress external
```

Set env vars with `--env-vars` or in the Azure portal.

## Health checks (optional but recommended)
If you add a health endpoint, configure your platform to call it:
- Example: `/health`
- Use the platform's health check settings (ECS target group, Cloud Run health checks, Azure Container Apps probes)

## Common settings
- `NODE_ENV=production`
- `PORT=3000` (or update your service to match your app)
- Database or cache URLs as required by your environment

## Troubleshooting
- Ensure the image is built for Linux/amd64 if your cloud runtime requires it:

```bash
docker buildx build --platform linux/amd64 -t comex-stat-api:latest .
```

- Check container logs in your platform's logging console if the service fails to start.
