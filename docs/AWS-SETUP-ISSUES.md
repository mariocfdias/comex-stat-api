# AWS Setup Issues and Solutions

## Date: 2026-01-30

This document describes the issues encountered during AWS ECS deployment and their solutions.

---

## Issue 1: Static Files Not Found (404 Errors)

### Symptom
```json
{
  "message": "Layer file for arrendamento not found at /usr/src/app/static/ARRENDAMENTO/ARRENDAMENTO.shp.",
  "error": "Not Found",
  "statusCode": 404
}
```

### Root Cause
The `static` directory containing GeoJSON and shapefile layers was **not being copied to the Docker runtime container**.

**Dockerfile before fix:**
```dockerfile
# Runtime stage - MISSING static directory!
COPY --from=builder /usr/src/app/package*.json ./
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/dist ./dist
# static directory was NOT copied!
```

### Solution
Added the static directory copy in the Dockerfile runtime stage:

```dockerfile
COPY --from=builder /usr/src/app/static ./static
```

**File:** `Dockerfile:37`

---

## Issue 2: ECS Not Deploying Updated Docker Image

### Symptom
Even after multiple deployments using `./deploy-to-aws.sh`, the production API still returned 404 errors for static files.

### Root Cause
The ECS task definition was **pinned to a specific image SHA256 digest** instead of using the `:latest` tag.

**Task definition configuration:**
- Image: `194133064894.dkr.ecr.us-east-2.amazonaws.com/sri/comexstat@sha256:c11ee2e4699904526e43cd30037794f6a4255f85af9ec052d0fd82f7453b55d0`
- This digest pointed to an **old image** without the static files

When running `--force-new-deployment`, ECS simply restarted tasks with the same old image digest, ignoring the newly pushed `:latest` tag in ECR.

### Solution
Updated the task definition to use the **`:latest` tag** instead of a SHA256 digest:

```bash
# Download current task definition
aws ecs describe-task-definition --task-definition comexstat-api-task --region us-east-2

# Update image reference from SHA digest to :latest tag
# Register new task definition revision (became revision 2)
aws ecs register-task-definition --cli-input-json file://updated-task-def.json

# Update service to use new revision
aws ecs update-service \
  --cluster elastic-zebra-c6v7sm \
  --service comexstat-api \
  --task-definition comexstat-api-task:2 \
  --force-new-deployment \
  --region us-east-2
```

**Result:** Service now uses `comexstat-api-task:2` which references the `:latest` tag, ensuring new deployments always pull the most recent image.

---

## Issue 3: SCM Data Download Timeout

### Symptom
```
[ERROR] [ScmCsvService] Attempt 1 failed:
connect ETIMEDOUT 200.198.193.243:443
```

Application attempts to download data from `https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip` but times out after 2 minutes.

### Root Causes Investigated

#### Network Configuration (All OK)
- ✅ Security Group egress: Allows all outbound traffic (`-1` protocol to `0.0.0.0/0`)
- ✅ VPC Route Table: Has Internet Gateway (`igw-0ef1cbb5e11d4a5a6`) for default route
- ✅ Subnets: All public with `MapPublicIpOnLaunch: True`
- ✅ ECS Tasks: Have `assignPublicIp: ENABLED`
- ✅ Network ACLs: Allow all inbound/outbound traffic

**Network setup was correct - not a firewall/routing issue.**

#### Application Timeout Configuration
- Connection timeout in code: `120000ms` (2 minutes)
- External server `app.anm.gov.br` (IP: 200.198.193.243) is slow to respond
- Possible throttling of AWS IP ranges by ANM server

### Solution: Pre-download Data During Docker Build

Instead of downloading at runtime from ECS (which has connectivity issues), download the data during the Docker build process on the local machine.

**Updated Dockerfile:**

```dockerfile
# Build stage - Added curl and unzip
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    python3 \
    make \
    g++ \
    curl \
    unzip \
  && rm -rf /var/lib/apt/lists/*

# Pre-download SCM data during build
RUN mkdir -p /usr/src/app/data/scm/extracted && \
    (curl -k --max-time 300 -o /tmp/microdados-scm.zip \
      https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip && \
     unzip -q /tmp/microdados-scm.zip -d /usr/src/app/data/scm/extracted && \
     rm /tmp/microdados-scm.zip && \
     echo "SCM data pre-downloaded successfully") || \
    echo "SCM data download skipped (will download at runtime if needed)"

# Runtime stage - Copy pre-downloaded data
COPY --from=builder /usr/src/app/data ./data
```

**Benefits:**
- Data is bundled in the Docker image
- No runtime download needed
- Avoids network timeout issues
- Falls back gracefully if download fails during build

---

## Issue 4: Docker Build Cache Preventing Updates

### Symptom
After updating the Dockerfile, running `./deploy-to-aws.sh` still deployed the old image without the fixes.

### Root Cause
The deploy script used `docker buildx build` **without the `--no-cache` flag**, causing Docker to use cached layers from before the Dockerfile changes.

### Solution
Updated `deploy-to-aws.sh` to force clean builds:

```bash
# Line 16 - Added --no-cache flag
docker buildx build --no-cache --platform linux/amd64 -t comex-stat-api:${IMAGE_TAG} .
```

---

## AWS Resources Configuration

### ECS Cluster
- Name: `elastic-zebra-c6v7sm`
- Region: `us-east-2`

### ECS Service
- Name: `comexstat-api`
- Task Definition: `comexstat-api-task:2` (using `:latest` tag)
- Desired Count: 1
- Running Count: 1

### ECR Repository
- Name: `sri/comexstat`
- URI: `194133064894.dkr.ecr.us-east-2.amazonaws.com/sri/comexstat`
- Latest Image Push: 2026-01-30 10:33:55

### VPC Configuration
- VPC ID: `vpc-09decfbdb21b443f8`
- Subnets:
  - `subnet-02f41cd742e13de61` (us-east-2b, public)
  - `subnet-0f53f8a8e0de861b9` (us-east-2a, public)
  - `subnet-028c1ea5324bbf639` (us-east-2c, public)
- Internet Gateway: `igw-0ef1cbb5e11d4a5a6`
- Security Group: `sg-02773a267e7174cce`

### Security Group Rules
**Ingress:**
- All traffic from self (security group)
- TCP 3000 from 0.0.0.0/0 (public access)

**Egress:**
- All protocols to 0.0.0.0/0 (unrestricted outbound)

**⚠️ Security Recommendation:**
For production, use an Application Load Balancer (ALB) and restrict port 3000 to only accept traffic from the ALB security group, not from the public internet.

---

## Deployment Commands Reference

### Build and Deploy to AWS
```bash
./deploy-to-aws.sh
```

### Manual Build (Local Testing)
```bash
docker build --no-cache -t comex-stat-api:latest .
docker run -p 3000:3000 comex-stat-api:latest
```

### Verify Static Files in Image
```bash
docker run --rm comex-stat-api:latest ls -la /usr/src/app/static/
```

### Check ECS Task Logs
```bash
aws logs tail /ecs/comexstat-api-task --region us-east-2 --since 5m --follow
```

### Force Service Redeployment
```bash
aws ecs update-service \
  --cluster elastic-zebra-c6v7sm \
  --service comexstat-api \
  --force-new-deployment \
  --region us-east-2
```

### Check Running Task
```bash
aws ecs list-tasks \
  --cluster elastic-zebra-c6v7sm \
  --service-name comexstat-api \
  --region us-east-2

aws ecs describe-tasks \
  --cluster elastic-zebra-c6v7sm \
  --tasks <TASK_ARN> \
  --region us-east-2
```

---

## Lessons Learned

1. **Always copy all required directories in multi-stage Docker builds**
   - Explicitly list all necessary directories (static, data, etc.)
   - Don't assume `COPY . .` in builder stage will transfer to runtime stage

2. **Use image tags instead of SHA digests for development**
   - Tags (`:latest`) allow easy updates
   - Digests pin to specific builds (good for production immutability, bad for rapid iteration)

3. **Use `--no-cache` when debugging Docker build issues**
   - Cached layers can hide Dockerfile changes
   - Essential after modifying COPY or RUN commands

4. **Pre-download data during build for unreliable external services**
   - Bake data into the image when possible
   - Reduces runtime dependencies and network issues

5. **Verify Docker image contents before deploying**
   - Use `docker run --rm <image> ls -la` to inspect
   - Saves time troubleshooting production issues

6. **Task definition updates require new revisions**
   - `--force-new-deployment` doesn't update the task definition
   - Must register new task definition and update service to use it

---

## Related Documentation

- [DEPLOYMENT-CLOUD.md](./DEPLOYMENT-CLOUD.md) - Cloud deployment guide
- [FIX-NETWORK-TIMEOUT.md](./FIX-NETWORK-TIMEOUT.md) - Network troubleshooting
- [Dockerfile](../Dockerfile) - Updated with fixes
- [deploy-to-aws.sh](../deploy-to-aws.sh) - Updated deployment script
