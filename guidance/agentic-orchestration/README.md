# Guidance for Agentic Intelligent Document Processing on AWS

## Table of Contents

1. [Overview](#overview)
2. [Cost](#cost)
3. [Prerequisites](#prerequisites)
4. [Deployment Steps](#deployment-steps)
5. [Deployment Validation](#deployment-validation)
6. [Running the Guidance](#running-the-guidance)
7. [Next Steps](#next-steps)
8. [Cleanup](#cleanup)
9. [FAQ, known issues, additional considerations, and limitations](#faq-known-issues-additional-considerations-and-limitations)
10. [Notices](#notices)
11. [Authors](#authors)

## Overview

Organizations process thousands of documents daily—purchase orders, invoices, contracts, and forms—each containing critical business information. Manual processing is slow, error-prone, and expensive. Traditional document processing solutions require extensive upfront configuration and struggle with document format variations.

This guidance demonstrates how to build an intelligent document processing (IDP) system using **Amazon Bedrock AgentCore** and AI agents. Unlike traditional IDP solutions, this agentic approach:

- **Learns and adapts**: AI agents iteratively improve extraction instructions based on validation feedback
- **Handles format variations**: Automatically adjusts to different document layouts without manual configuration
- **Self-corrects errors**: Troubleshooter agents identify and fix extraction issues automatically
- **Scales horizontally**: Add new document types by providing sample documents and schemas

Key benefits:
- **Automated document classification and data extraction** using vector similarity search
- **Self-improving accuracy** through agent-based troubleshooting and instruction refinement
- **Minimal upfront configuration** - provide sample documents and JSON schemas
- **Serverless, scalable architecture** built on AWS managed services
- **Lower maintenance costs** compared to traditional commercial IDP solutions

The system uses a multi-agent orchestration pattern where specialized agents collaborate to process documents:
- **Analyzer Agent**: Extracts text and identifies sender, document type (PO, invoice, etc.)
- **Matcher Agent**: Finds similar documents using vector search
- **Instructions Agent**: Generates extraction prompts from sample documents (training workflow)
- **Extractor Agent**: Extracts structured data following instructions
- **Validator Agent**: Validates extracted data against schemas and business rules
- **Troubleshooter Agent**: Analyzes validation failures and suggests fixes (processing workflow)
- **Instructions Fixer Agent**: Updates extraction instructions based on troubleshooter feedback (training workflow)
- **Save Instructions Agent**: Persists successful instructions for reuse

<img src="AgenticIDP-Reference-Architecture/infrastructure.png" width="1200" />

## Cost

You are responsible for the cost of the AWS services used while running this Guidance. As of January 2026, the cost for running this Guidance with the default settings in the US East Region is approximately **$58 per month** for training 10 documents and processing 1,000 documents.

We recommend creating a [Budget](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html) through [AWS Cost Explorer](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/) to help manage costs. Prices are subject to change. For full details, refer to the pricing webpage for each AWS service used in this Guidance.

### Sample Cost Table

The following table provides a sample cost breakdown for deploying this Guidance with the default parameters in the US East (N. Virginia) Region for one month.

#### Base Infrastructure Cost (Monthly)

| AWS Service | Dimensions | Cost [USD] |
|-------------|------------|------------|
| Amazon S3 | S3 Standard storage (1 GB), S3 Vectors (0.5 GB) | $0.04 |
| Amazon DynamoDB | Standard table, 0.1 GB storage | $0.03 |
| Amazon Aurora DSQL | 0.5 GB storage | $0.17 |
| Amazon ECR | 0.5 GB storage | $0.05 |
| Amazon CloudWatch | Logs storage (0.2 GB) | $0.01 |
| **Base Infrastructure Subtotal** | | **$0.30** |

#### Training Cost (One-Time per Document Type)

Training 10 sample documents to create reusable instructions for a document type.

| AWS Service | Dimensions | Cost [USD] |
|-------------|------------|------------|
| Amazon Bedrock - Claude 4.5 Sonnet | 230K input tokens, 80K output tokens | $1.89 |
| Amazon Bedrock - Claude 4.5 Haiku | 170K input tokens, 40K output tokens | $0.37 |
| Amazon Bedrock - Nova 2 Lite | 21K input tokens, 1K output tokens | $0.01 |
| Amazon Bedrock AgentCore Runtime | 1.83 GB-hours (11 min per doc × 10 docs) | $0.03 |
| Amazon Bedrock AgentCore Gateway | 205 tool invocations (20.5 per doc × 10 docs) | $0.001 |
| Amazon S3 Vectors | 10 search operations, 10 add operations | $0.25 |
| Amazon Aurora DSQL | 1,500 DPUs (validation + save) | $0.01 |
| AWS Lambda | 10 invocations, 512 MB, 1s execution | $0.00 |
| **Training Subtotal (10 documents)** | | **$2.56** |

#### Processing Cost (Ongoing)

Processing 1,000 documents using existing instructions (after training). Assumes 10% require troubleshooting.

| AWS Service | Dimensions | Cost [USD] |
|-------------|------------|------------|
| Amazon Bedrock - Claude 4.5 Haiku | 20M input tokens, 3.5M output tokens | $37.50 |
| Amazon Bedrock - Claude 4.5 Sonnet | 2.3M input tokens (troubleshooter, 10% of docs) | $6.90 |
| Amazon Bedrock - Nova 2 Lite | 8.5M input tokens, 0.5M output tokens | $3.80 |
| Amazon Bedrock AgentCore Runtime | 75 GB-hours (4.5 min per doc × 1,000 docs) | $1.09 |
| Amazon Bedrock AgentCore Gateway | 10,600 tool invocations (10.6 per doc × 1,000 docs) | $0.05 |
| Amazon S3 Vectors | 1,000 search operations | $5.00 |
| Amazon Aurora DSQL | 80K DPUs (validation only) | $0.64 |
| AWS Lambda | 1,000 invocations, 512 MB, 1s execution | $0.01 |
| Amazon S3 | 4,000 GET requests, 3,000 PUT requests | $0.02 |
| Amazon DynamoDB | 13,000 read/write units | $0.01 |
| **Processing Subtotal (1,000 documents)** | | **$55.02** |

#### Total Monthly Cost

| Component | Cost [USD] |
|-----------|------------|
| Base Infrastructure | $0.30 |
| Training (10 documents) | $2.56 |
| Processing (1,000 documents) | $55.02 |
| **Total** | **$57.88** |

**Notes:**
- Training is a one-time cost per document type (vendor, supplier, form type)
- Processing costs scale linearly at $0.055 per document
- 10% of documents require troubleshooting (validation errors)
- Foundation models (Bedrock) represent 85% of total cost
- All compute services (Lambda, AgentCore, Aurora DSQL) scale to zero when idle

## Prerequisites

You will need an AWS account to use this solution. Sign up for an account [here](https://aws.amazon.com/resources/create-account/).

This guidance uses serverless AWS services and can be deployed from Linux/macOS/Windows systems.

### Installing infrastructure tools

1. Clone the repository:
   ```bash
   git clone https://github.com/aws-samples/aws-ai-intelligent-document-processing.git
   cd agenticidp-guidance
   ```

2. Install the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

3. Install [Node.js](https://nodejs.org/) 18+ and npm.

4. Install Python 3.11+ and the [uv package manager](https://docs.astral.sh/uv/getting-started/installation/)

5. Install [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)


### AWS account requirements

This guidance uses **Amazon Bedrock AgentCore** with Amazon Nova and Anthropic models via **Amazon Bedrock**. Your account must have:

1. **Service access**: Ensure your account has access to:
   - Amazon Bedrock 
   - Amazon Bedrock AgentCore Runtime
   - Amazon Bedrock AgentCore Gateway
   - Amazon Bedrock AgentCore Identity
   - Amazon S3 Vector Buckets
   - Amazon Aurora DSQL

3. **IAM permissions**: Your AWS credentials need permissions to create:
   - S3 buckets
   - Lambda functions
   - DynamoDB tables
   - Cognito user pools
   - ECR repositories
   - ECS Fargate services
   - CloudFormation stacks

### Service limits

Your AWS account has default quotas, also known as service limits, described [here](https://docs.aws.amazon.com/general/latest/gr/aws_service_limits.html). This guidance can be installed and tested within the default quotas for each of the services used.

To operate this guidance at scale, monitor your usage and configure alarms when quotas are close to being exceeded. Details on visualizing service quotas and setting alarms are [here](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Quotas-Visualize-Alarms.html).

### Supported Regions

Deploy this guidance only in AWS regions that support:
- Amazon Bedrock AgentCore (Runtime, Gateway, Identity)
- Amazon S3 Vector Buckets
- Amazon Aurora DSQL
- Amazon Bedrock with Anthropic Claude and Amazon Nova models

Recommended regions:
- US East (N. Virginia) - us-east-1
- US West (Oregon) - us-west-2
- Europe (Ireland) - eu-west-1
- Asia Pacific (Tokyo) - ap-northeast-1

## Deployment Steps

### 1. Configure AWS credentials

```bash
aws configure
```

### 2. Bootstrap CDK (first time only)

```bash
cdk bootstrap
```

### 3. Set up Python environment

```bash
# Create virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
```

### 4. Install UI dependencies

```bash
cd ui/orchestrator
npm install
cd ../..
```

### 5. Configure admin email (optional)

To skip the email prompt during deployment, add your admin email to `cdk.context.json`:

```json
{
  "agenticidp": {
    "development": {
      "environment": "dev",
      "app_name": "agenticidp",
      "admin_email": "your-email@example.com"
    }
  }
}
```

### 6. Deploy the solution

**Quick Deploy (Recommended)**:
```bash
uv run deploy.py
```

This automated script:
1. Deploys all CDK stacks (Core, Gateway, Aurora, Agent, UI Orchestrator, UI infrastructure)
2. Fetches CloudFormation outputs
3. Builds the UI with correct configuration
4. Deploys UI to S3/CloudFront

**Options**:
```bash
uv run deploy.py --env prod    # Deploy to production
uv run deploy.py --skip-ui     # Deploy only CDK stacks (skip UI build)
uv run deploy.py --admin-email your-email@example.com  # Specify admin email
uv run deploy.py --help        # Show all options
```

**Manual Deployment (Alternative)**:

If you prefer to deploy manually:

1. Deploy CDK stacks:
   ```bash
   cdk deploy --all --require-approval never
   ```

2. Build and deploy UI:
   ```bash
   cd ui/orchestrator
   npm run deploy:cdk:dev
   ```

**Deployed stacks**:
- **AgenticIDP-Core-Dev**: S3 buckets (documents, vectors), Cognito, DynamoDB, Parameter Store
- **AgenticIDP-Gateway-Dev**: Lambda functions, ECR repositories, Bedrock AgentCore Gateway
- **AgenticIDP-Aurora-Dev**: Aurora DSQL cluster, sample data loader
- **AgenticIDP-Agent-Dev**: Bedrock AgentCore Runtime, agent containers
- **AgenticIDP-UIOrchestr-Dev**: API Gateway endpoints for UI
- **AgenticIDP-ModernUI-Dev**: React UI on S3/CloudFront

Deployment takes approximately 15-20 minutes.

## Deployment Validation

### 1. Verify CloudFormation stacks

Open the CloudFormation console and verify all stacks show `CREATE_COMPLETE` status:
- AgenticIDP-Core-Dev
- AgenticIDP-Gateway-Dev
- AgenticIDP-Aurora-Dev
- AgenticIDP-Agent-Dev
- AgenticIDP-UIOrchestr-Dev
- AgenticIDP-ModernUI-Dev

### 2. Verify DynamoDB tables

Navigate to DynamoDB console and confirm these tables exist:
- `idp-jobs` table with:
  - Partition key: `job_id` (STRING)
  - Three global secondary indexes
- `idp-instructions` table with:
  - Partition key: `instruction_id` (STRING)

### 3. Verify S3 buckets

Confirm these S3 buckets were created:
- `agenticidp-objects-{account-id}` - Document storage
- `agenticidp-instructions-{account-id}` - Extraction instructions
- `agenticidp-results-{account-id}` - Processing results
- `agenticidp-ui-{account-id}` - UI assets
- `agenticidp-vectors-{account-id}` - Vector embeddings (S3 Vector Bucket)

### 4. Verify Cognito User Pool

Navigate to Cognito console and confirm:
- User pool: `agenticidp-gateway-pool`
- App clients: `agenticidp-gateway-client`, `agenticidp-ui-client`

### 5. Verify Bedrock AgentCore Resources

Run the following CLI commands to verify resources:

```bash
# Verify gateway
aws bedrock-agent-runtime list-gateways

# Verify agent runtime
aws bedrock-agent-runtime list-agents
```

You should see `agenticidp-tool-gateway` and `agenticidp-orchestrator-agent` in the outputs.

### 6. Verify Aurora DSQL cluster

```bash
aws dsql list-clusters
```

You should see the `agenticidp-dsql-cluster` with status `ACTIVE`.

### 7. Verify Lambda functions

Navigate to Lambda console and confirm these functions exist:
- `agenticidp-po-validator` - Purchase order validation
- `agenticidp-matcher` - Document matching
- Additional tool functions for agent operations

### 8. Verify CloudFront distribution

Navigate to CloudFront console and confirm the distribution for the UI is deployed and enabled.

### 6. Get the UI URL

The UI URL is available in the CloudFormation outputs:
```bash
aws cloudformation describe-stacks --stack-name AgenticIDP-ModernUI-Dev \
  --query 'Stacks[0].Outputs[?OutputKey==`UIUrl`].OutputValue' --output text
```

## Running the Guidance

This guidance includes sample purchase order documents for testing. We'll validate the system by uploading sample documents and verifying the processing results.

### 1. Access the web UI

After deployment completes, you will receive an email at the address provided during deployment. This email contains:
- CloudFront URL for the web application
- Username for initial login
- Temporary password

On first login, you will be required to change your password.

### 2. Upload sample documents

The application provides three main features:

#### Option 1: Process Document
- **Purpose**: Test document processing workflow
- **Usage**: Upload a file from the training folder
- **Sample files**: Use files from `infrastructure/sample_data/purchase_orders/training/`
- **What it does**: Processes the document through the complete agent workflow:
  1. **Analyzer Agent**: Extracts text and identifies sender name, address, and document type
  2. **Matcher Agent**: Searches for similar documents using vector similarity
  3. **Training workflow** (if no match found):
     - Instructions Agent → Extractor Agent → Validator Agent
     - If validation fails: Instructions Fixer Agent → Extractor Agent → Validator Agent (loop)
     - If validation passes: Save Instructions Agent
  4. **Processing workflow** (if match found):
     - Extractor Agent → Validator Agent
     - If validation fails: Troubleshooter Agent → Validator Agent (loop)
     - If validation passes: Complete

#### Option 2: Review Jobs and Instructions
- View processing history and results
- Inspect extraction instructions for each document type
- Review validation results and error messages
- Track document processing status

#### Option 3: Interactive Chat
- **Purpose**: Multi-turn conversation with the orchestrator agent
- **Usage**: Type messages and get responses
- **Sample questions**:
  - `what tools do you have`
  - `list instructions`
  - `what is the status of job XXXX`
  - `what went wrong with job XXXX, how can we update the instructions?`
- **What it does**: Maintains conversation context across multiple exchanges

### 3. Verify processing results

After uploading a document, you can:

1. **Check job status** in the "Review Jobs and Instructions" tab
2. **View extracted data** in the job details
3. **Inspect validation results** to see if data passed schema and business rule validation
4. **Review instructions** to see the extraction prompt generated for this document type

### 4. Understanding the agent workflows

**All documents start with**:
```
Upload → Analyzer Agent (extract text, identify sender/type) → Matcher Agent
```

**Training workflow** (new document type - no match found):
```
Matcher (no match) → Instructions Agent → Extractor → Validator
  ↓ (if validation fails)
Instructions Fixer → Extractor → Validator (loop until valid)
  ↓ (if validation passes)
Save Instructions Agent → Complete
```

**Processing workflow** (known document type - match found):
```
Matcher (match found) → Extractor → Validator
  ↓ (if validation fails)
Troubleshooter → Validator (loop until valid)
  ↓ (if validation passes)
Complete
```

**Key differences**:
- **Training**: Uses Instructions Agent and Instructions Fixer Agent to create/refine extraction instructions
- **Processing**: Uses Troubleshooter Agent to fix data issues without changing instructions

### 5. Sample validation results

The validation results include:
- Schema validation: Checks if extracted data matches expected JSON structure
- Business rule validation: Validates against reference data (vendors, products)
- Field-level validation: Checks individual field formats and values

## Agent Workflow Details

This guidance uses a multi-agent orchestration pattern where specialized agents collaborate to process documents. Each agent has a specific role in the workflow:

### 1. Analyzer Agent
**Purpose**: Extract text from documents and identify key metadata

**How it works**:
- Receives uploaded document (PDF, image, etc.)
- Uses Amazon Textract to extract text and layout information
- Analyzes extracted text to identify:
  - Sender name and address
  - Document type (purchase order, invoice, contract, etc.)
  - Document format characteristics
- Passes extracted text and metadata to Matcher Agent

**Tools used**:
- `textract_analyze_document`: Extract text and layout from documents
- `update_job`: Update job with extracted text and metadata

### 2. Matcher Agent
**Purpose**: Find similar documents using vector similarity search

**How it works**:
- Receives extracted text and metadata from Analyzer Agent
- Searches S3 Vector Bucket for similar documents using cosine similarity
- If match found (similarity > threshold):
  - Returns document ID and instructions S3 URI from matched record
  - Workflow proceeds to **Processing workflow** with existing instructions
- If no match found:
  - Workflow proceeds to **Training workflow** to create new instructions

**Tools used**:
- `search_documents`: Vector similarity search in S3 Vector Bucket
- `get_job`: Retrieve current job details from DynamoDB
- `update_job`: Update job with match results

### 3. Instructions Agent
**Purpose**: Generate extraction instructions for new document formats (Training workflow only)

**How it works**:
- Receives markdown text extracted from document
- Analyzes document structure and field patterns
- Uses minimal prompt approach: starts with JSON schema + essential clarifications
- Generates extraction instructions in markdown format
- Saves instructions to S3 at `instructions/{session_id}/extraction_prompt.md`
- Updates job with instructions S3 URI

**Key features**:
- Minimal initial instructions (schema-focused)
- Lets troubleshooter handle iterative refinements
- Avoids over-specification on first attempt

**Tools used**:
- `download_file`: Retrieve document text from S3
- `upload_file`: Save generated instructions to S3
- `update_job`: Update job with instructions URI

### 4. Extractor Agent
**Purpose**: Extract structured data from documents following instructions

**How it works**:
- Receives markdown document text and instructions S3 URI
- Downloads extraction instructions from S3
- Follows instructions to extract structured data
- Outputs JSON matching the schema defined in instructions
- Saves extracted data to S3
- Updates job with extracted data S3 URI

**Key features**:
- Instruction-driven extraction (not hardcoded rules)
- Produces structured JSON output
- Handles various document formats using same agent

**Tools used**:
- `download_file`: Retrieve document text and instructions from S3
- `upload_file`: Save extracted JSON to S3
- `update_job`: Update job with extraction results

### 5. Validator Agent
**Purpose**: Validate extracted data against schemas and business rules

**How it works**:
- Receives extracted data S3 URI
- Downloads extracted JSON
- Performs two-level validation:
  1. **Schema validation**: Checks JSON structure matches expected schema
  2. **Business rule validation**: Validates against reference data in Aurora DSQL
     - Vendor validation: Checks vendor exists and is active
     - Product validation: Checks SKUs exist and prices match
     - Line item validation: Validates quantities, units, totals
- Returns validation result with pass/fail status and detailed error messages

**Validation outcomes**:
- `VALID`: All checks passed, workflow complete
- `INVALID_SCHEMA`: Schema validation failed, proceed to Troubleshooter
- `INVALID_DATA`: Business rule validation failed, proceed to Troubleshooter

**Tools used**:
- `download_file`: Retrieve extracted JSON from S3
- `validate_purchase_order`: Validate against Aurora DSQL reference data
- `update_job`: Update job with validation results

### 6. Instructions Fixer Agent
**Purpose**: Fix extraction instructions when validation fails during training (Training workflow only)

**Model**: Claude 4.5 Sonnet

**How it works**:
- Receives validation error messages from Validator Agent
- Downloads original markdown document and current extraction instructions
- Analyzes validation errors against the PO schema:
  - Schema validation errors (missing fields, wrong types)
  - Content mapping errors (incorrect field mappings)
- Generates revised extraction instructions to fix the errors
- Saves updated instructions to S3 at `instructions/[session_id]/extraction_prompt.md`
- Updates job with new instructions URI
- Workflow returns to Extractor Agent with revised instructions

**Key features**:
- Iterative refinement during training phase
- Focuses on improving instructions, not fixing data
- Preserves working parts of instructions while fixing problems
- Uses PO schema as reference for correct structure

**Tools used**:
- `download_file`: Retrieve markdown document and current instructions
- `upload_file`: Save revised instructions to S3
- `get_job`: Retrieve validation error details
- `update_job`: Update job with new instructions URI

### 7. Troubleshooter Agent
**Purpose**: Fix extracted JSON data when validation fails during processing (Processing workflow only)

**Model**: Claude 4.5 Sonnet

**How it works**:
- Receives validation error messages from Validator Agent
- Downloads original markdown document and extracted JSON data
- Analyzes validation errors:
  - Schema errors: Fixes JSON structure to pass schema validation
  - Content errors: Ensures all data from markdown is correctly mapped
- Corrects the extracted JSON directly (does not modify instructions)
- Saves corrected JSON to S3
- Updates job with corrected data URI
- Workflow returns to Validator Agent with fixed JSON

**Key features**:
- One-time fix for individual documents during processing
- Fixes data, not instructions (instructions already exist)
- Handles both schema and content validation errors
- Uses PO schema as reference for correct structure

**Tools used**:
- `download_file`: Retrieve markdown document and extracted JSON
- `upload_file`: Save corrected JSON to S3
- `get_job`: Retrieve validation error details
- `update_job`: Update job with corrected data URI

### 8. Save Instructions Agent
**Purpose**: Persist successful extraction instructions for reuse

**How it works**:
- Receives validated extraction results and instructions
- Extracts document properties (type, sender, format characteristics)
- Creates or updates vector record in S3 Vector Bucket:
  - Stores document embeddings for similarity search
  - Links to instructions S3 URI
  - Includes metadata (document type, sender, processing workflow)
- Enables future documents with similar format to reuse instructions

**Key features**:
- Builds knowledge base of document formats
- Enables zero-shot processing of similar documents
- Reduces processing time for known formats

**Tools used**:
- `add_document`: Add new document to vector bucket
- `update_document`: Update existing document record
- `update_job`: Update job with document ID

### Agent Orchestration Flow

The orchestrator agent coordinates these specialized agents using a graph-based workflow:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Document Processing Graph                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Upload Document                                                │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────┐                                                   │
│  │ Analyzer │ (extract text, identify sender/type)              │
│  └──────────┘                                                   │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────┐                                                    │
│  │ Matcher │                                                    │
│  └─────────┘                                                    │
│       │                                                         │
│       ├──────────────────────────────────┐                      │
│       │                                  │                      │
│   No Match                          Match Found                 │
│       │                                  │                      │
│       ▼                                  ▼                      │
│  ┌──────────────┐                   ┌───────────┐               │
│  │ Instructions │                   │ Extractor │               │
│  │    Agent     │                   │   Agent   │               │
│  └──────────────┘                   └───────────┘               │
│       │                                  │                      │
│       ▼                                  ▼                      │
│  ┌───────────┐◄──┐                 ┌───────────┐                │
│  │ Extractor │   │                 │ Extractor │                │
│  │   Agent   │   │                 │   Agent   │                │
│  └───────────┘   │                 └───────────┘                │
│       │          │                      │                       │
│       ▼          │                      ▼                       │
│  ┌───────────┐   │                 ┌───────────┐◄───┐           │
│  │ Validator │   │                 │ Validator │    │           │
│  │   Agent   │   │                 │   Agent   │    │           │
│  └───────────┘   │                 └───────────┘    │           │
│       │          │                      │           │           │
│   ┌───┴───┐      │              ┌───────┴───────┐   │           │
│   │       │      │              │               │   │           │
│ Valid  Invalid   │           Valid          Invalid │           │
│   │       │      │              │               │   │           │
│   │       ▼      │              │               ▼   │           │
│   │  ┌────────────────┐         │  ┌────────────────┐           │
│   │  │ Instructions   │         │  │ Troubleshooter │           │
│   │  │ Fixer Agent    │         │  │     Agent      │           │
│   │  └────────────────┘         │  └────────────────┘           │
│   │                             │                               │
│   │                             ▼                               │
│   ▼                        Complete                             │
│  ┌────────────┐                                                 │
│  │    Save    │                                                 │
│  │Instructions│                                                 │
│  └────────────┘                                                 │
│       │                                                         │
│       ▼                                                         │
│  Complete                                                       │
└─────────────────────────────────────────────────────────────────┘
```

**Key workflow characteristics**:
- **Analyzer always first**: Extracts text and identifies document metadata
- **Two distinct workflows**: Training (no match) vs Processing (match found)
- **Training workflow**: Instructions Agent → Extractor → Validator → Instructions Fixer (loop) → Save Instructions
- **Processing workflow**: Extractor → Validator → Troubleshooter (loop)
- **Knowledge persistence**: Save Instructions stores successful patterns for reuse
- **Self-improving**: Each failure improves instructions (training) or fixes data issues (processing)

## Next Steps

### Integration with External Systems
The document processing solution can be integrated with external business systems:
- **ERP integration**: Push purchase orders to SAP, Oracle, NetSuite
- **CRM integration**: Send extracted customer data to Salesforce, HubSpot
- **Content management**: Store processed documents in SharePoint, Box
- **Workflow automation**: Trigger approvals in ServiceNow, Jira

### Adding New Document Types
To add support for new document types:
1. Create JSON schema defining the expected output structure
2. Create a validator for your document type (identify what document charasteristics need validation)
3. Test with sample documents for your document type

### Custom Validation Rules
To add business-specific validation:
1. Modify the Validator Agent to include custom checks
2. Create validation rules in a validator Lambda

## Cleanup

To remove all deployed resources:

### 1. Run cleanup script

```bash
uv run destroy.py
```

Or manually delete stacks:

```bash
cdk destroy --all
```

### 2. Verify cleanup

Check CloudFormation console to ensure all stacks are deleted:
- AgenticIDP-ModernUI-Dev
- AgenticIDP-UIOrchestr-Dev
- AgenticIDP-Agent-Dev
- AgenticIDP-Aurora-Dev
- AgenticIDP-Gateway-Dev
- AgenticIDP-Core-Dev

## FAQ, known issues, additional considerations, and limitations

### FAQ

**Q: What document formats are supported?**
A: The system supports any document format that Amazon Textract can process, including PDF, PNG, JPEG, and TIFF. The agent-based approach adapts to different document layouts automatically.

**Q: How accurate is the extraction?**
A: Accuracy improves over time as the system processes more documents. Initial extraction may require 1-2 iterations of troubleshooting and instruction refinement. Once instructions are refined, similar documents achieve high accuracy.

**Q: Can I use different foundation models?**
A: Yes, you can configure different models in `utils/config.py`. The system is designed to work with any Amazon Bedrock foundation model that supports function calling.

**Q: How do I add new document types?**
A: To add support for new document types:
1. Create a JSON schema defining your document structure (see `agents/orchestratorgraph/doc_schema/purchase_order_schema.json` as example)
2. Create a validation Lambda function for your document type (see `infrastructure/lambda/po_validator/` for reference)
3. Update agent prompts that reference "purchase order" to your document type:
   - `agents/orchestratorgraph/prompts/po_minimal_instructions_prompt.txt`
   - `agents/orchestratorgraph/prompts/po_meta_system_prompt.txt`
   - Validator agent system prompt in `agents/orchestratorgraph/validator_agent.py`
4. Update validation logic - the current validator checks SKUs and vendors against synthetic demo data in Aurora DSQL. Replace this with your own business validation rules.

**Q: What happens if extraction fails repeatedly?**
A: The system allows up to 10 loop iterations per workflow (configured via `set_max_node_executions(10)` in the orchestrator). If validation continues to fail after 10 attempts, the workflow exits with an error status. Users can then:
- Use the chat functionality to review the job status and error messages
- Manually update extraction instructions via the UI
- Reprocess the failed job with updated instructions
The troubleshooter provides detailed analysis in each iteration to help identify and fix issues.

### Known Issues

- **Windows compatibility**: This solution works on Linux/macOS. Windows users may need WSL or Git Bash
- **Cold start latency**: First invocation of agents may take 30-60 seconds due to container cold starts
- **Token limits**: Very large documents may exceed model context windows

### Additional Considerations

When building your own Generative AI application, review and consider the [OWASP Top 10 for LLMs and Generative AI Apps](https://genai.owasp.org/llm-top-10/).

**Security best practices**:
- Enable MFA for Cognito users
- Restrict S3 bucket access using bucket policies
- Use VPC endpoints for private connectivity
- Enable CloudTrail logging for audit trails
- Rotate Cognito client secrets regularly

**Cost optimization**:
- Use S3 Intelligent-Tiering for document storage
- Configure DynamoDB auto-scaling based on usage
- Use Fargate Spot for non-production environments
- Set CloudWatch log retention policies

**Performance optimization**:
- Increase Lambda memory for faster processing
- Use provisioned concurrency for predictable latency
- Batch document uploads for higher throughput
- Cache frequently accessed instructions

## Notices

The dataset utilized in this guidance consists entirely of synthetic data. This artificial data is designed to mimic real-world information but does not contain any actual personal or sensitive information.

*Customers are responsible for making their own independent assessment of the information in this Guidance. This Guidance: (a) is for informational purposes only, (b) represents AWS current product offerings and practices, which are subject to change without notice, and (c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided "as is" without warranties, representations, or conditions of any kind, whether express or implied. AWS responsibilities and liabilities to its customers are controlled by AWS agreements, and this Guidance is not part of, nor does it modify, any agreement between AWS and its customers.*


