#!/bin/bash
set -e

# Configuration
ECR_REGISTRY="194133064894.dkr.ecr.us-east-2.amazonaws.com"
ECR_REPOSITORY="sri/comexstat"
AWS_REGION="us-east-2"
IMAGE_TAG="${1:-latest}"

echo "🚀 Deploying comex-stat-api to AWS ECS"
echo "======================================"

# Step 1: Build the Docker image for Linux/amd64
echo ""
echo "📦 Step 1: Building Docker image..."
docker buildx build --no-cache --platform linux/amd64 -t comex-stat-api:${IMAGE_TAG} .

# Step 2: Tag for ECR
echo ""
echo "🏷️  Step 2: Tagging image for ECR..."
docker tag comex-stat-api:${IMAGE_TAG} ${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}

# Step 3: Login to ECR
echo ""
echo "🔐 Step 3: Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${ECR_REGISTRY}

# Step 4: Push to ECR
echo ""
echo "⬆️  Step 4: Pushing image to ECR..."
docker push ${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}

# Step 5: Get ECS cluster and service info
echo ""
echo "🔍 Step 5: Finding ECS services..."
CLUSTERS=$(aws ecs list-clusters --region ${AWS_REGION} --query 'clusterArns[*]' --output text)

if [ -z "$CLUSTERS" ]; then
    echo "❌ No ECS clusters found in region ${AWS_REGION}"
    exit 1
fi

for CLUSTER_ARN in $CLUSTERS; do
    CLUSTER_NAME=$(basename ${CLUSTER_ARN})
    echo "   Checking cluster: ${CLUSTER_NAME}"

    SERVICES=$(aws ecs list-services --cluster ${CLUSTER_NAME} --region ${AWS_REGION} --query 'serviceArns[*]' --output text)

    for SERVICE_ARN in $SERVICES; do
        SERVICE_NAME=$(basename ${SERVICE_ARN})
        echo "   Found service: ${SERVICE_NAME}"

        # Optional: Update service with new deployment
        read -p "   Deploy to ${SERVICE_NAME}? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Get current task definition
            TASK_DEF_ARN=$(aws ecs describe-services \
              --cluster ${CLUSTER_NAME} \
              --services ${SERVICE_NAME} \
              --region ${AWS_REGION} \
              --query 'services[0].taskDefinition' \
              --output text)

            echo "   📋 Registering new task definition revision (current: ${TASK_DEF_ARN})..."

            # Get task definition JSON and update image, then register new revision
            NEW_TASK_DEF=$(aws ecs describe-task-definition \
              --task-definition ${TASK_DEF_ARN} \
              --region ${AWS_REGION} \
              --query 'taskDefinition' \
              --output json | \
              python3 -c "
import json, sys
td = json.load(sys.stdin)
new_image = '${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}'
for c in td.get('containerDefinitions', []):
    if '${ECR_REPOSITORY}' in c.get('image', ''):
        c['image'] = new_image
# Remove read-only fields
for field in ['taskDefinitionArn','revision','status','requiresAttributes','compatibilities','registeredAt','registeredBy']:
    td.pop(field, None)
print(json.dumps(td))
")

            NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
              --cli-input-json "${NEW_TASK_DEF}" \
              --region ${AWS_REGION} \
              --query 'taskDefinition.taskDefinitionArn' \
              --output text)

            echo "   🔄 Deploying ${SERVICE_NAME} with new task def: ${NEW_TASK_DEF_ARN}..."
            aws ecs update-service \
              --cluster ${CLUSTER_NAME} \
              --service ${SERVICE_NAME} \
              --task-definition ${NEW_TASK_DEF_ARN} \
              --force-new-deployment \
              --region ${AWS_REGION} > /dev/null
            echo "   ✅ Deployment triggered for ${SERVICE_NAME}"
        fi
    done
done

echo ""
echo "✨ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Monitor deployment: aws ecs describe-services --cluster <CLUSTER> --services <SERVICE> --region ${AWS_REGION}"
echo "   2. Check logs in CloudWatch"
echo "   3. If still timing out, check network configuration (see docs/FIX-NETWORK-TIMEOUT.md)"
