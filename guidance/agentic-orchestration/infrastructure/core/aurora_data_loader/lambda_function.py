#!/usr/bin/env python3
"""Lambda to load sample data into Aurora DSQL cluster."""
import json
import boto3
import psycopg2
import csv
import io
import urllib3

def lambda_handler(event, context):
    # Log full request immediately for debugging
    print("="*80)
    print("FULL REQUEST EVENT:")
    print(json.dumps(event, indent=2, default=str))
    print("="*80)
    
    response_url = event['ResponseURL']
    request_id = event['RequestId']
    logical_resource_id = event['LogicalResourceId']
    stack_id = event['StackId']
    
    try:
        request_type = event['RequestType']
        cluster_id = event['ResourceProperties']['ClusterId']
        region = event['ResourceProperties']['Region']
        bucket_name = event['ResourceProperties']['BucketName']
        
        dsql_client = boto3.client('dsql', region_name=region)
        
        # Get cluster info and wait for ACTIVE status
        cluster_info = dsql_client.get_cluster(identifier=cluster_id)
        cluster_status = cluster_info['status']
        
        if cluster_status != 'ACTIVE':
            raise Exception(f"Cluster is not ready. Status: {cluster_status}")
            
        endpoint = f"{cluster_id}.dsql.{region}.on.aws"
        
        # Generate auth token
        auth_token = dsql_client.generate_db_connect_admin_auth_token(
            Hostname=endpoint,
            Region=region,
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
        
        if request_type in ['Create', 'Update']:
            load_data(conn, bucket_name)
            create_readonly_role(conn)
        elif request_type == 'Delete':
            drop_tables(conn)
            
        conn.close()
        
        # Send success response
        send_response(response_url, {
            'Status': 'SUCCESS',
            'RequestId': request_id,
            'LogicalResourceId': logical_resource_id,
            'StackId': stack_id,
            'PhysicalResourceId': f'data-loader-{cluster_id}',
            'Data': {'Endpoint': endpoint}
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        # Send failure response
        send_response(response_url, {
            'Status': 'FAILED',
            'RequestId': request_id,
            'LogicalResourceId': logical_resource_id,
            'StackId': stack_id,
            'PhysicalResourceId': f'data-loader-{cluster_id if "cluster_id" in locals() else "unknown"}',
            'Reason': str(e)
        })

def send_response(response_url, response_data):
    """Send response to CloudFormation"""
    http = urllib3.PoolManager()
    response_body = json.dumps(response_data).encode('utf-8')
    
    try:
        response = http.request(
            'PUT',
            response_url,
            body=response_body,
            headers={'Content-Type': 'application/json'}
        )
        print(f"Response sent: {response.status}")
    except Exception as e:
        print(f"Failed to send response: {e}")

def drop_tables(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS products")
    conn.commit()
    cursor.execute("DROP TABLE IF EXISTS retailers")
    conn.commit()
    cursor.close()

def load_data(conn, bucket_name):
    cursor = conn.cursor()
    s3_client = boto3.client('s3')
    
    # Drop and recreate tables
    drop_tables(conn)
    
    # Create products table - separate transaction
    cursor.execute('''
        CREATE TABLE products (
            sku VARCHAR(50) PRIMARY KEY,
            category VARCHAR(100),
            product_name VARCHAR(200),
            description TEXT,
            msrp DECIMAL(10,2),
            wholesale_price DECIMAL(10,2),
            options TEXT
        )
    ''')
    conn.commit()
    
    # Create retailers table - separate transaction
    cursor.execute('''
        CREATE TABLE retailers (
            account_number VARCHAR(50) PRIMARY KEY,
            company_name VARCHAR(200),
            contact_name VARCHAR(100),
            email VARCHAR(100),
            phone VARCHAR(20),
            street_address VARCHAR(200),
            city VARCHAR(100),
            state VARCHAR(10),
            zip_code VARCHAR(20),
            business_type VARCHAR(50),
            order_minimum DECIMAL(10,2),
            credit_limit DECIMAL(10,2),
            template_type VARCHAR(50),
            logo_path VARCHAR(500)
        )
    ''')
    conn.commit()
    
    # Load products - separate transaction
    try:
        products_obj = s3_client.get_object(Bucket=bucket_name, Key='products.csv')
        products_csv = products_obj['Body'].read().decode('utf-8')
        products_reader = csv.DictReader(io.StringIO(products_csv))
        
        for row in products_reader:
            cursor.execute('''
                INSERT INTO products (sku, category, product_name, description, msrp, wholesale_price, options)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (
                row['sku'], row['category'], row['product_name'], row['description'],
                float(row['msrp']) if row['msrp'] else None,
                float(row['wholesale_price']) if row['wholesale_price'] else None,
                row['options']
            ))
        conn.commit()
        print(f"Loaded {cursor.rowcount} products")
    except Exception as e:
        print(f"Error loading products: {e}")
    
    # Load retailers - separate transaction
    try:
        retailers_obj = s3_client.get_object(Bucket=bucket_name, Key='retailers.csv')
        retailers_csv = retailers_obj['Body'].read().decode('utf-8')
        retailers_reader = csv.DictReader(io.StringIO(retailers_csv))
        
        for row in retailers_reader:
            cursor.execute('''
                INSERT INTO retailers (account_number, company_name, contact_name, email, phone,
                                     street_address, city, state, zip_code, business_type,
                                     order_minimum, credit_limit, template_type, logo_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                row['account_number'], row['company_name'], row['contact_name'], row['email'],
                row['phone'], row['street_address'], row['city'], row['state'], row['zip_code'],
                row['business_type'],
                float(row['order_minimum']) if row['order_minimum'] else None,
                float(row['credit_limit']) if row['credit_limit'] else None,
                row['template_type'], row['logo_path']
            ))
        conn.commit()
        print(f"Loaded {cursor.rowcount} retailers")
    except Exception as e:
        print(f"Error loading retailers: {e}")
    
    cursor.close()

def create_readonly_role(conn):
    """Create generic read-only database role for any IAM role to use"""
    cursor = conn.cursor()
    
    try:
        # Create database role with LOGIN
        cursor.execute("CREATE ROLE readonly WITH LOGIN")
        conn.commit()
        print("Created readonly database role")
        
        # Grant SELECT on tables
        cursor.execute("GRANT USAGE ON SCHEMA public TO readonly")
        cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly")
        conn.commit()
        print("Granted SELECT permissions to readonly role")
        
    except Exception as e:
        print(f"Error creating read-only role: {e}")
        # Don't fail if role already exists
    finally:
        cursor.close()
