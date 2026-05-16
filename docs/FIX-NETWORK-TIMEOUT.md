# Fixing Network Timeout in AWS ECS

## Root Cause
Your ECS container can't connect to external HTTPS servers (app.anm.gov.br:443) due to network configuration.

## Solution 1: Fix AWS Security Groups & VPC

### 1. Check Security Group
Your ECS task needs an **outbound rule** allowing HTTPS:
- Type: HTTPS
- Protocol: TCP
- Port: 443
- Destination: 0.0.0.0/0 (or specific IP: 200.198.193.243/32)

```bash
# View current security group
aws ec2 describe-security-groups --group-ids <YOUR_SG_ID>

# Add outbound HTTPS rule if missing
aws ec2 authorize-security-group-egress \
  --group-id <YOUR_SG_ID> \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0
```

### 2. Check VPC/Subnet Configuration

If running in a **private subnet**, you need either:

**Option A: NAT Gateway (recommended for production)**
- Create a NAT Gateway in a public subnet
- Route private subnet traffic to NAT Gateway
- Allows outbound internet access while keeping tasks private

```bash
# Create NAT Gateway (must be in public subnet)
aws ec2 create-nat-gateway \
  --subnet-id <PUBLIC_SUBNET_ID> \
  --allocation-id <ELASTIC_IP_ALLOCATION_ID>

# Update route table for private subnet
aws ec2 create-route \
  --route-table-id <PRIVATE_ROUTE_TABLE_ID> \
  --destination-cidr-block 0.0.0.0/0 \
  --nat-gateway-id <NAT_GATEWAY_ID>
```

**Option B: Move to Public Subnet (simpler, less secure)**
- Update ECS service to use public subnets
- Enable "Auto-assign public IP"

### 3. Check Network ACLs
Ensure your subnet's Network ACL allows outbound HTTPS:
```bash
aws ec2 describe-network-acls --filters "Name=association.subnet-id,Values=<SUBNET_ID>"
```

## Solution 2: Alternative Download Method

If you can't change AWS network config, download the file through your CI/CD pipeline:

### A. Pre-download in build process

Add to your Dockerfile:
```dockerfile
# Add this before the final stage
RUN curl -k -o /tmp/microdados-scm.zip \
  https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip \
  && mkdir -p /usr/src/app/data/scm/extracted \
  && unzip /tmp/microdados-scm.zip -d /usr/src/app/data/scm/extracted \
  && rm /tmp/microdados-scm.zip
```

### B. Use Lambda function to download
Create a Lambda function in a public subnet that downloads the file to S3, then your ECS task reads from S3.

### C. Use EFS mount
- Download file to EFS volume from a machine with internet access
- Mount EFS volume to ECS task

## Solution 3: Deploy Updated Code

Your container is still running old code. Deploy the new version:

```bash
# Build for Linux/amd64
docker buildx build --platform linux/amd64 -t comex-stat-api:latest .

# Tag for ECR
docker tag comex-stat-api:latest 194133064894.dkr.ecr.us-east-2.amazonaws.com/sri/comexstat:latest

# Login to ECR
aws ecr get-login-password --region us-east-2 | \
  docker login --username AWS --password-stdin 194133064894.dkr.ecr.us-east-2.amazonaws.com

# Push to ECR
docker push 194133064894.dkr.ecr.us-east-2.amazonaws.com/sri/comexstat:latest

# Force ECS to deploy new version
aws ecs update-service \
  --cluster <YOUR_CLUSTER> \
  --service <YOUR_SERVICE> \
  --force-new-deployment \
  --region us-east-2
```

## Quick Diagnosis Commands

```bash
# From inside ECS container (exec into running task)
curl -v -I --max-time 10 https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip

# Check DNS resolution
nslookup app.anm.gov.br

# Check basic connectivity
ping -c 3 8.8.8.8

# Test HTTPS to any site
curl -I https://www.google.com
```

## Recommended Approach

1. **Immediate fix**: Add NAT Gateway or move to public subnet with auto-assign public IP
2. **Code update**: Deploy the new code with retry logic (already done)
3. **Long-term**: Consider pre-downloading during build or using S3 caching

## Testing

After fixing network config, test from ECS task:
```bash
# Execute into running task
aws ecs execute-command \
  --cluster <YOUR_CLUSTER> \
  --task <TASK_ID> \
  --container comexstat-api \
  --command "/bin/bash" \
  --interactive

# Then inside the container:
curl -k -I https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip
```
