#!/usr/bin/env python3

import logging
import os
import sys
import time
import json
import requests
import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name="us-east-1")


def parse_args():
    if len(sys.argv) < 4:
        log.error("Usage: python stage_books.py <book_list_file> <index_path> <bucket_name>")
        sys.exit(1)
        
    return sys.argv[1], sys.argv[2], sys.argv[3]


def download_books(list_file, dest_dir="books"):
    os.makedirs(dest_dir, exist_ok=True)
    file_paths = []
    
    with open(list_file, "r") as f:
        urls = [line.strip() for line in f if line.strip()]
        
    for url in urls:
        filename = url.split("/")[-1]
        dest_path = os.path.join(dest_dir, filename)
        file_paths.append(dest_path)
        
        if os.path.exists(dest_path):
            log.info(f"Skipping existing file: {dest_path}")
            continue
            
        log.info(f"Downloading {url} to {dest_path}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(dest_path, "wb") as out_file:
                out_file.write(response.content)
                
        except requests.RequestException as e:
            log.error(f"Error downloading {url}: {e}")
            
        time.sleep(1)
        
    return file_paths


def create_bucket(bucket):
    try:
        s3.head_bucket(Bucket=bucket)
        log.info(f"Bucket {bucket} already exists.")
        return True
    except ClientError:
        log.info(f"Bucket {bucket} not found. Creating it...")
        try:
            s3.create_bucket(Bucket=bucket)
            log.info(f"Successfully created bucket {bucket}.")
            return True
        except ClientError as e:
            log.error(f"Error creating bucket {bucket}: {e}")
            return False


def make_public(bucket):
    try:
        s3.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": False,
                "IgnorePublicAcls": False,
                "BlockPublicPolicy": False,
                "RestrictPublicBuckets": False,
            },
        )
        
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket}/*",
                }
            ],
        }
        
        s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        log.info(f"Successfully made bucket {bucket} public.")
        return True
    except ClientError as e:
        log.error(f"Error making bucket {bucket} public: {e}")
        return False


def upload_files(bucket, file_paths):
    uploaded_count = 0
    for path in file_paths:
        key = os.path.basename(path)
        log.info(f"Uploading {path} to s3://{bucket}/{key}")
        try:
            s3.upload_file(
                path,
                bucket,
                key,
                ExtraArgs={"ContentType": "text/plain; charset=utf-8"}
            )
            uploaded_count += 1
        except ClientError as e:
            log.error(f"Error uploading {path}: {e}")
    return uploaded_count


def upload_index(bucket, index_path):
    try:
        log.info(f"Uploading {index_path} to s3://{bucket}/index.html")
        s3.upload_file(
            index_path,
            bucket,
            "index.html",
            ExtraArgs={"ContentType": "text/html"}
        )
        return True
    except ClientError as e:
        log.error(f"Error uploading index page: {e}")
        return False


def main():
    list_file, index_path, bucket = parse_args()
    
    file_paths = download_books(list_file)
    if not file_paths:
        log.error("No books were downloaded. Exiting.")
        sys.exit(1)
        
    if not create_bucket(bucket):
        sys.exit(1)
        
    if not make_public(bucket):
        sys.exit(1)
        
    uploaded = upload_files(bucket, file_paths)
    if uploaded == 0:
        log.error("No files were successfully uploaded. Exiting.")
        sys.exit(1)
        
    if not upload_index(bucket, index_path):
        sys.exit(1)
        
    log.info(f"Success! Public URL: https://{bucket}.s3.amazonaws.com/index.html")


if __name__ == "__main__":
    main()
