import json
import logging
import traceback
import boto3
import psycopg2
import os
from decimal import Decimal
from typing import Dict, Any, List, Optional
from jsonschema import validate, ValidationError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
REGION = os.environ.get('AWS_REGION', 'us-east-1')
CLUSTER_ID = os.environ.get('CLUSTER_ID', 'demo-cluster')
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET_NAME')

# Load PO schema
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'purchase_order_schema.json')
with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
    PO_SCHEMA = json.load(f)

# Initialize S3 client
s3_client = boto3.client('s3', region_name=REGION)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Main Lambda handler for PO validation"""
    logger.info(f"Incoming event: {json.dumps(event, default=str)}")
    
    try:
        # Get tool name from context
        tool_name = context.client_context.custom['bedrockAgentCoreToolName']
        
        # Remove target prefix if present
        delimiter = "___"
        if delimiter in tool_name:
            tool_name = tool_name[tool_name.index(delimiter) + len(delimiter):]
        
        logger.info(f"Processing tool: {tool_name}")
        
        if tool_name == 'validate_purchase_order':
            return validate_purchase_order(event)
        else:
            return create_error_response(f"Unknown tool: {tool_name}")
            
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return create_error_response(f"Tool execution failed: {str(e)}")

def create_success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create success response"""
    return {
        "statusCode": 200,
        "body": json.dumps(data, default=str)
    }

def create_error_response(error_message: str) -> Dict[str, Any]:
    """Create error response"""
    return {
        "statusCode": 400,
        "body": json.dumps({"error": error_message, "success": False})
    }

def download_po_from_s3(key_path: str) -> Dict[str, Any]:
    """Download and parse PO JSON from S3 using configured bucket"""
    try:
        if not DOCUMENT_BUCKET:
            raise ValueError("DOCUMENT_BUCKET_NAME environment variable not set")
        
        logger.info(f"Downloading from bucket: {DOCUMENT_BUCKET}, key: {key_path}")
        
        # Download file
        response = s3_client.get_object(Bucket=DOCUMENT_BUCKET, Key=key_path)
        content = response['Body'].read().decode('utf-8')
        
        # Parse JSON
        po_data = json.loads(content)
        logger.info(f"Successfully parsed JSON from S3")
        
        return po_data
        
    except Exception as e:
        logger.warning(f"Error downloading from S3: {str(e)}")
        raise

def validate_po_schema(po_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate PO data against JSON schema"""
    try:
        validate(instance=po_data, schema=PO_SCHEMA)
        logger.info("PO data passed schema validation")
        return {"valid": True, "errors": []}
        
    except ValidationError as e:
        logger.error(f"Schema validation failed: {e.message}")
        return {
            "valid": False,
            "errors": [{
                "field": ".".join(str(p) for p in e.path) if e.path else "root",
                "message": e.message
            }]
        }
    except Exception as e:
        logger.error(f"Unexpected validation error: {str(e)}")
        return {
            "valid": False,
            "errors": [{"field": "unknown", "message": str(e)}]
        }

def connect_to_aurora_dsql() -> psycopg2.extensions.connection:
    """Connect to Aurora DSQL cluster"""
    try:
        logger.info(f"Connecting to Aurora DSQL cluster: {CLUSTER_ID}")
        
        dsql_client = boto3.client('dsql', region_name=REGION)
        
        # Get cluster info
        cluster_info = dsql_client.get_cluster(identifier=CLUSTER_ID)
        cluster_status = cluster_info['status']
        
        if cluster_status != 'ACTIVE':
            raise Exception(f"Cluster is not ready. Status: {cluster_status}")
            
        endpoint = f"{CLUSTER_ID}.dsql.{REGION}.on.aws"
        logger.info(f"Cluster endpoint: {endpoint}")
        
        # Generate auth token
        auth_token = dsql_client.generate_db_connect_admin_auth_token(
            Hostname=endpoint,
            Region=REGION,
            ExpiresIn=3600
        )
        
        # Connect to database
        conn = psycopg2.connect(
            host=endpoint,
            port=5432,
            database='postgres',
            user='admin',
            password=auth_token,
            sslmode='require'
        )
        
        logger.info("Successfully connected to Aurora DSQL")
        return conn
        
    except Exception as e:
        logger.warning(f"Failed to connect to Aurora DSQL: {str(e)}")
        logger.warning(f"Connection traceback: {traceback.format_exc()}")
        raise

def validate_purchase_order(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Validate purchase order against Aurora DSQL database"""
    try:
        key_path = parameters.get('key_path')
        if not key_path:
            return create_error_response("Missing required parameter: key_path")
        
        logger.info(f"Validating PO from S3 key: {key_path}")
        
        # Download PO from S3
        try:
            po_data = download_po_from_s3(key_path)
        except Exception as e:
            return create_error_response(f"Failed to download PO from S3: {str(e)}")
        
        # Validate against JSON schema
        schema_validation = validate_po_schema(po_data)
        if not schema_validation['valid']:
            return create_success_response({
                "validation_status": "INVALID",
                "schema_errors": schema_validation['errors'],
                "line_item_results": [],
                "company_validation": {"status": "SKIPPED", "issues": []},
                "summary": {
                    "total_items": 0,
                    "valid_items": 0,
                    "invalid_items": 0,
                    "warnings": 0
                },
                "success": False
            })
        
        # Connect to database
        conn = connect_to_aurora_dsql()
        
        try:
            # Extract data for validation
            line_items = po_data.get('line_items', [])
            customer_data = {
                'name': po_data.get('retailer_name', ''),
                'address': po_data.get('customer_address', '')
            }
            
            # Validate line items (SKUs)
            line_items_result = validate_skus_batch(conn, line_items)
            
            # Validate company information
            company_result = validate_company_info(conn, customer_data)
            
            # Calculate summary
            total_items = len(line_items)
            valid_items = sum(1 for item in line_items_result if item['status'] == 'VALID')
            invalid_items = sum(1 for item in line_items_result if item['status'] == 'INVALID')
            warnings = sum(1 for item in line_items_result if item['status'] == 'WARNING')
            
            # Determine overall status
            if invalid_items > 0 or company_result['status'] == 'INVALID':
                overall_status = 'INVALID'
            elif warnings > 0 or company_result['status'] == 'WARNING':
                overall_status = 'WARNING'
            else:
                overall_status = 'VALID'
            
            result = {
                "validation_status": overall_status,
                "schema_validation": "PASSED",
                "line_item_results": line_items_result,
                "company_validation": company_result,
                "summary": {
                    "total_items": total_items,
                    "valid_items": valid_items,
                    "invalid_items": invalid_items,
                    "warnings": warnings
                },
                "success": True
            }
            
            logger.info(f"Validation completed: {overall_status}, {valid_items}/{total_items} items valid")
            return create_success_response(result)
            
        finally:
            conn.close()
            logger.info("Database connection closed")
            
    except Exception as e:
        logger.error(f"Error validating purchase order: {str(e)}")
        logger.error(f"Validation traceback: {traceback.format_exc()}")
        return create_error_response(f"Error validating purchase order: {str(e)}")

def validate_skus_batch(conn: psycopg2.extensions.connection, line_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate SKUs in batch using efficient IN query"""
    try:
        if not line_items:
            logger.info("No line items to validate")
            return []
        
        # Extract SKUs for batch query
        skus = [item.get('sku') for item in line_items if item.get('sku')]
        logger.info(f"Validating {len(skus)} SKUs: {skus}")

        if not skus:
            return [{"sku": "N/A", "status": "INVALID", "issues": [{"field": "sku", "severity": "ERROR", "message": "SKU is required"}]}]

        # Get all available SKUs for error messages
        cursor = conn.cursor()
        cursor.execute("SELECT sku FROM products ORDER BY sku")
        all_skus = [row[0] for row in cursor.fetchall()]
        
        # Batch query for all SKUs
        query = """
            SELECT sku, wholesale_price, options, product_name
            FROM products 
            WHERE sku IN %s
        """
        
        logger.info(f"Executing SKU query: {query}")
        cursor.execute(query, (tuple(skus),))
        db_products = {row[0]: {'wholesale_price': row[1], 'options': row[2], 'product_name': row[3]} 
                      for row in cursor.fetchall()}
        
        logger.info(f"Found {len(db_products)} products in database")
        
        # Validate each line item
        results = []
        for item in line_items:
            sku = item.get('sku')
            result = validate_single_sku(item, db_products.get(sku), all_skus)
            results.append(result)
            
        cursor.close()
        return results
        
    except Exception as e:
        logger.warning(f"Error in batch SKU validation: {str(e)}")
        logger.warning(f"SKU validation traceback: {traceback.format_exc()}")
        raise

def validate_single_sku(line_item: Dict[str, Any], db_product: Optional[Dict[str, Any]], all_skus: List[str]) -> Dict[str, Any]:
    """Validate a single SKU against database product"""
    sku = line_item.get('sku', 'N/A')
    issues = []
    
    # Check if SKU exists
    if not db_product:
        return {
            "sku": sku,
            "status": "INVALID",
            "issues": [{
                "field": "sku",
                "severity": "ERROR",
                "message": f"SKU '{sku}' not found in product catalog. Available SKUs: {', '.join(all_skus[:10])}{'...' if len(all_skus) > 10 else ''}"
            }]
        }
    
    # Validate price
    unit_price = line_item.get('unit_price')
    wholesale_price = db_product.get('wholesale_price')
    
    if unit_price and wholesale_price:
        # Convert to float for comparison
        unit_price = float(unit_price)
        wholesale_price = float(wholesale_price)
        
        if unit_price > wholesale_price:
            issues.append({
                "field": "unit_price",
                "severity": "ERROR",
                "message": f"Price ${unit_price} exceeds wholesale price ${wholesale_price}",
                "suggested_value": str(wholesale_price)
            })
        elif unit_price < wholesale_price * 0.8:  # Warning if significantly below wholesale
            issues.append({
                "field": "unit_price",
                "severity": "WARNING",
                "message": f"Price ${unit_price} is significantly below wholesale price ${wholesale_price}"
            })
    
    # Validate options (parse JSON and check specific fields)
    db_options = db_product.get('options', '')
    line_item_options = line_item.get('options', {})
    
    if db_options:
        try:
            options_data = json.loads(db_options)
            
            # Check colors
            color = line_item_options.get('colors')
            if color and 'colors' in options_data:
                if color not in options_data['colors']:
                    issues.append({
                        "field": "options.colors",
                        "severity": "ERROR",
                        "message": f"Color '{color}' not available. Available colors: {', '.join(options_data['colors'])}"
                    })
            
            # Check sizes
            size = line_item_options.get('sizes')
            if size and 'sizes' in options_data:
                if size not in options_data['sizes']:
                    issues.append({
                        "field": "options.sizes",
                        "severity": "ERROR",
                        "message": f"Size '{size}' not available. Available sizes: {', '.join(options_data['sizes'])}"
                    })
                        
        except json.JSONDecodeError:
            # Fallback to old string-based validation if JSON parsing fails
            for option_field in ['colors', 'sizes', 'battery', 'brake_type']:
                if line_item_options.get(option_field) and option_field not in db_options.lower():
                    issues.append({
                        "field": f"options.{option_field}",
                        "severity": "WARNING",
                        "message": f"Option '{option_field}' may not be available for this product"
                    })
    
    # Determine status
    if any(issue['severity'] == 'ERROR' for issue in issues):
        status = 'INVALID'
    elif any(issue['severity'] == 'WARNING' for issue in issues):
        status = 'WARNING'
    else:
        status = 'VALID'
    
    return {
        "sku": sku,
        "status": status,
        "issues": issues,
        "product_name": db_product.get('product_name')
    }

def validate_company_info(conn: psycopg2.extensions.connection, customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate company information against retailers table"""
    try:
        company_name = customer_data.get('name', '').strip()
        if not company_name:
            return {
                "status": "INVALID",
                "issues": [{
                    "field": "customer.name",
                    "severity": "ERROR",
                    "message": "Company name is required"
                }]
            }
        
        logger.info(f"Validating company: {company_name}")
        
        # Get all available companies for error messages
        cursor = conn.cursor()
        cursor.execute("SELECT company_name FROM retailers ORDER BY company_name")
        all_companies = [row[0] for row in cursor.fetchall()]
        
        # Query for company match
        query = """
            SELECT account_number, company_name, street_address, city, state
            FROM retailers 
            WHERE LOWER(company_name) LIKE LOWER(%s)
        """
        
        cursor.execute(query, [f'%{company_name}%'])
        matches = cursor.fetchall()
        
        logger.info(f"Found {len(matches)} company matches")
        
        issues = []
        matched_retailer = None
        
        if not matches:
            issues.append({
                "field": "customer.name",
                "severity": "ERROR",
                "message": f"Company '{company_name}' not found in retailer database. Available companies: {', '.join(all_companies[:10])}{'...' if len(all_companies) > 10 else ''}"
            })
            status = 'INVALID'
        else:
            # Use first match
            matched_retailer = matches[0][0]  # account_number
            db_address = f"{matches[0][2]}, {matches[0][3]}, {matches[0][4]}".strip()
            
            # Validate address if provided
            customer_address = customer_data.get('address', '').strip()
            if customer_address:
                if customer_address.lower() not in db_address.lower() and db_address.lower() not in customer_address.lower():
                    issues.append({
                        "field": "customer.address",
                        "severity": "WARNING",
                        "message": f"Address may not match retailer records. Expected: {db_address}"
                    })
            
            status = 'WARNING' if issues else 'VALID'
        
        cursor.close()
        
        return {
            "status": status,
            "matched_retailer": matched_retailer,
            "issues": issues
        }
        
    except Exception as e:
        logger.error(f"Error validating company info: {str(e)}")
        logger.error(f"Company validation traceback: {traceback.format_exc()}")
        return {
            "status": "INVALID",
            "issues": [{
                "field": "customer",
                "severity": "ERROR",
                "message": f"Error validating company information: {str(e)}"
            }]
        }
