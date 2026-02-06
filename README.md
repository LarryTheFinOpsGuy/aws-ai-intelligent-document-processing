# AWS AI Intelligent Document Processing

This repository provides comprehensive solutions for Intelligent Document Processing (IDP) using AWS AI services. It contains both official guidance implementations and workshop materials to help you automate document processing workflows.

## Projects

### Official Guidance

#### 1. [Agentic Intelligent Document Processing](./guidance/agentic-orchestration)

An advanced IDP system using **Amazon Bedrock AgentCore** and AI agents that learns and adapts to document variations. Unlike traditional IDP solutions, this agentic approach self-corrects errors and improves extraction accuracy through iterative feedback loops.

**Key Features:**
- Multi-agent orchestration with specialized agents (Analyzer, Matcher, Extractor, Validator, Troubleshooter)
- Self-improving accuracy through agent-based instruction refinement
- Minimal upfront configuration - provide sample documents and JSON schemas
- Handles format variations automatically without manual configuration
- Serverless, scalable architecture built on AWS managed services

**Technologies:** Amazon Bedrock AgentCore, Amazon S3 Vectors, Amazon Aurora DSQL, AWS Lambda, Amazon DynamoDB

[View Documentation →](./guidance/agentic-orchestration/README.md)

---

#### 2. [Prompt Flow Orchestration for IDP](./guidance/prompt-flow-orchestration)

A prompt-based IDP solution leveraging **Amazon Bedrock Prompt Flows** to orchestrate document classification, extraction, and validation workflows. This guidance uses foundation models with structured prompts to handle various document types with minimal customization.

**Key Features:**
- Automated document classification and data extraction
- Multi-stage validation with Amazon A2I human review integration
- Document-specific extraction flows (Driver's License, URLA, Bank Statements)
- Handles complex, variable document formats
- Event-driven serverless architecture

**Technologies:** Amazon Bedrock, Amazon Textract, Amazon A2I, AWS Lambda, Amazon SQS, Amazon SNS, Amazon DynamoDB

[View Documentation →](./guidance/prompt-flow-orchestration/README.md)

---

### Workshops (Legacy)

#### 3. [IDP Workshop Materials](./workshops)

Hands-on workshop materials covering the fundamentals of Intelligent Document Processing with AWS AI services. These workshops provide step-by-step Jupyter notebooks to familiarize yourself with core IDP concepts and AWS services.

**Topics Covered:**
- Document classification
- Document extraction with Amazon Textract
- Document enrichment with Amazon Comprehend
- Human-in-the-loop review with Amazon A2I
- Document processing at scale
- Industry-specific use cases
- Entity training and Gen AI integration

**Technologies:** Amazon Textract, Amazon Comprehend, Amazon A2I, Amazon SageMaker

[View Workshop →](./workshops/README.md)

---

## Getting Started

Choose the solution that best fits your needs:

- **For agentic IDP with self-improving accuracy:** Start with [Agentic Orchestration](./guidance/agentic-orchestration)
- **For prompt-based IDP with human review:** Start with [Prompt Flow Orchestration](./guidance/prompt-flow-orchestration)
- **For learning IDP fundamentals:** Start with [Workshop Materials](./workshops)

Each project contains detailed deployment instructions, prerequisites, and usage examples.

## Architecture Overview

All solutions follow the core phases of an IDP pipeline:

1. **Classification** - Identify document types
2. **Extraction** - Extract structured data from documents
3. **Enrichment** - Enhance extracted data with additional context
4. **Validation** - Verify accuracy and completeness
5. **Human Review** - Manual review when needed

## Prerequisites

- AWS Account with appropriate service access
- AWS CLI installed and configured
- Basic familiarity with AWS services

Specific requirements vary by project - see individual README files for details.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for information on reporting security issues.

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file.

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and contribute to the project.

## Code of Conduct

This project has adopted the [Amazon Open Source Code of Conduct](CODE_OF_CONDUCT.md). For more information see the Code of Conduct FAQ or contact opensource-codeofconduct@amazon.com with any additional questions or comments.

---

## Disclaimer

The datasets utilized in these solutions consist entirely of synthetic data designed to mimic real-world information but do not contain any actual personal or sensitive information.

*Customers are responsible for making their own independent assessment of the information in this repository. This content: (a) is for informational purposes only, (b) represents current AWS product offerings and practices, which are subject to change without notice, and (c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided "as is" without warranties, representations, or conditions of any kind, whether express or implied.*
