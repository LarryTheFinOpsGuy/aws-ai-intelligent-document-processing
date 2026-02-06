# Aurora DSQL Demo

This demo script showcases Amazon Aurora DSQL capabilities by:

1. **Creating a cluster** (if it doesn't already exist)
2. **Connecting** to the cluster using IAM authentication
3. **Creating a table** with sample employee data
4. **Querying** the data with aggregations

## Prerequisites

- Python 3.8+
- AWS CLI configured with appropriate credentials
- Required IAM permissions (see below)

## Required IAM Permissions

Your AWS identity needs these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dsql:CreateCluster",
                "dsql:ListClusters",
                "dsql:GetCluster",
                "dsql:DbConnectAdmin",
                "dsql:TagResource"
            ],
            "Resource": "*"
        }
    ]
}
```

## Quick Start

1. **Setup the environment:**
   ```bash
   ./setup.sh
   ```

2. **Run the demo:**
   ```bash
   python3 aurora_dsql_demo.py
   ```

## What the Script Does

### 1. Cluster Management
- Checks if a cluster named `demo-cluster` exists
- Creates a new cluster if none exists
- Waits for the cluster to become `ACTIVE`

### 2. Authentication
- Generates an IAM authentication token (valid for 1 hour)
- Uses the token as the password for PostgreSQL connection

### 3. Database Operations
- Creates an `employees` table with sample data
- Inserts 5 sample employee records
- Queries all employees and shows department summaries

### 4. Sample Output
```
🚀 Aurora DSQL Demo Starting...
==================================================
Initializing AWS clients...
Checking if cluster 'demo-cluster' exists...
Cluster 'demo-cluster' already exists with status: ACTIVE
Cluster endpoint: 01abc2ldefg3hijklmnopqurstu.dsql.us-east-1.on.aws
Generating authentication token...
Connecting to Aurora DSQL cluster...
Creating sample table...
Inserting sample data...
Sample data loaded successfully!

=== All Employees ===
ID  Name            Department   Salary     Hire Date
------------------------------------------------------------
1   Alice Johnson   Engineering  $95000.0   2023-01-15
2   Bob Smith       Marketing    $75000.0   2023-02-20
3   Carol Davis     Engineering  $105000.0  2022-11-10
4   David Wilson    Sales        $85000.0   2023-03-05
5   Eve Brown       HR           $70000.0   2023-01-30

Total employees: 5

=== Department Summary ===
Department   Count  Avg Salary
-----------------------------------
Engineering  2      $100,000.00
HR           1      $70,000.00
Marketing    1      $75,000.00
Sales        1      $85,000.00

✅ Demo completed successfully!
Database connection closed.
```

## Key Features Demonstrated

- **Serverless Architecture**: No infrastructure management required
- **IAM Authentication**: Secure, token-based authentication
- **PostgreSQL Compatibility**: Standard SQL operations work seamlessly
- **Automatic Scaling**: Handles varying workloads automatically
- **High Availability**: Built-in redundancy and failover

## Configuration

You can modify these variables in `aurora_dsql_demo.py`:

- `CLUSTER_NAME`: Name of the Aurora DSQL cluster
- `REGION`: AWS region for the cluster
- `DATABASE_NAME`: Database name (always `postgres` for Aurora DSQL)
- `USERNAME`: Database username (always `admin` for Aurora DSQL)

## Cleanup

To delete the demo cluster:

```bash
aws dsql delete-cluster --identifier demo-cluster --region us-east-1
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Ensure your AWS credentials have the required permissions
2. **Connection Timeouts**: Check your network connectivity and security groups
3. **Token Expiration**: The script generates fresh tokens, but manual connections need new tokens every hour

### Useful Commands

```bash
# List all clusters
aws dsql list-clusters --region us-east-1

# Get cluster details
aws dsql get-cluster --identifier demo-cluster --region us-east-1

# Generate auth token manually
aws dsql generate-db-connect-admin-auth-token \
  --region us-east-1 \
  --expires-in 3600 \
  --hostname your-cluster-endpoint
```

## Learn More

- [Aurora DSQL Documentation](https://docs.aws.amazon.com/aurora-dsql/)
- [Getting Started Guide](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/getting-started.html)
- [Authentication and Authorization](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/authentication-authorization.html)
