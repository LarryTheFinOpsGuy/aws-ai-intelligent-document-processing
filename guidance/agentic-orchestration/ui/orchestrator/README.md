# Modern Orchestrator UI

A React-based web application for document processing orchestration, built with Vite and AWS Cloudscape Design System.

## Quick Start

### Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Run tests
npm test
```

### Production Build

```bash
# Build for production
npm run build:prod

# Preview production build
npm run preview
```

## Deployment

### Prerequisites

- Node.js 18+ 
- AWS CLI configured
- CDK stacks deployed (Core, Agent, UI Orchestrator)

### Deployment Options

#### Option 1: CDK-Integrated Deployment (Recommended)

Automatically retrieves configuration from deployed CDK stacks:

```bash
# Deploy to development
npm run deploy:cdk:dev

# Deploy to staging  
npm run deploy:cdk:staging

# Deploy to production
npm run deploy:cdk:prod
```

#### Option 2: Standalone Deployment

Deploy to existing UI hosting infrastructure:

```bash
# Deploy to development
npm run deploy:dev

# Deploy to staging
npm run deploy:staging

# Deploy to production
npm run deploy:prod
```

### Deployment Validation

Test your deployment configuration:

```bash
# Quick validation
npm run test:deployment

# Full validation with build test
npm run test:deployment:full
```

### Getting the Deployed URL

After deployment, you can get the application URL in several ways:

```bash
# Get URL for any environment
npm run get-url:dev      # Development URL
npm run get-url:staging  # Staging URL  
npm run get-url:prod     # Production URL

# Open the application in your browser
npm run open-app:dev     # Open development app
npm run open-app:staging # Open staging app
npm run open-app:prod    # Open production app

# Manual AWS CLI command
aws cloudformation describe-stacks \
  --stack-name UI-Dev-hosting \
  --region us-west-2 \
  --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" \
  --output text
```

## Environment Configuration

The application uses environment-specific configuration files:

- `.env.development` - Development settings
- `.env.staging` - Staging settings
- `.env.production` - Production settings

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `VITE_AWS_REGION` | AWS region |
| `VITE_COGNITO_USER_POOL_ID` | Cognito User Pool ID |
| `VITE_COGNITO_USER_POOL_CLIENT_ID` | Cognito App Client ID |
| `VITE_COGNITO_IDENTITY_POOL_ID` | Cognito Identity Pool ID |
| `VITE_API_BASE_URL` | API Gateway base URL |

## Architecture

### Technology Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **AWS Cloudscape** - UI component library
- **AWS Amplify** - Authentication
- **Axios** - HTTP client

### Build System

- **Development**: Fast builds with source maps
- **Production**: Optimized builds with minification and code splitting
- **Code Splitting**: Automatic chunking for optimal loading
- **Caching**: Long-term caching for static assets

### Deployment Pipeline

1. **Build Phase**: Compile TypeScript, bundle assets, optimize for production
2. **Configuration Phase**: Inject environment-specific settings
3. **Upload Phase**: Deploy to S3 with optimal caching headers
4. **Invalidation Phase**: Clear CloudFront cache for immediate updates

## Development

### Project Structure

```
ui/orchestrator/
├── src/                    # Source code
│   ├── components/         # React components
│   ├── services/          # API clients and utilities
│   ├── hooks/             # Custom React hooks
│   └── utils/             # Utility functions
├── scripts/               # Build and deployment scripts
├── build/                 # Production build output
└── public/                # Static assets
```

### Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run build:dev` | Build for development |
| `npm run build:staging` | Build for staging |
| `npm run build:prod` | Build for production |
| `npm run test` | Run tests |
| `npm run lint` | Run ESLint |
| `npm run deploy:cdk:dev` | CDK deployment to development |
| `npm run test:deployment` | Validate deployment configuration |
| `npm run get-url:dev` | Get development application URL |
| `npm run get-url:staging` | Get staging application URL |
| `npm run get-url:prod` | Get production application URL |
| `npm run open-app:dev` | Open development app in browser |
| `npm run open-app:staging` | Open staging app in browser |
| `npm run open-app:prod` | Open production app in browser |

### Code Quality

- **ESLint**: Code linting and formatting
- **TypeScript**: Static type checking
- **Prettier**: Code formatting (via ESLint)
- **Vitest**: Unit testing framework

## Troubleshooting

### Common Issues

**Build Failures**
- Check Node.js version (18+ required)
- Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Check for TypeScript errors: `npx tsc --noEmit`

**Deployment Failures**
- Verify AWS credentials: `aws sts get-caller-identity`
- Check CDK stack status: `cdk list`
- Validate environment configuration: `npm run test:deployment`

**Runtime Issues**
- Check browser console for errors
- Verify API endpoints are accessible
- Confirm Cognito configuration is correct

### Getting Help

1. Check the [Deployment Guide](./DEPLOYMENT.md) for detailed instructions
2. Review build and deployment logs for specific error messages
3. Validate your environment configuration
4. Contact the development team for support

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Run tests: `npm test`
4. Run linting: `npm run lint`
5. Test deployment configuration: `npm run test:deployment`
6. Submit a pull request

## License

This project is part of the AgenticIDP demonstration application.

---

For detailed deployment instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md).