import boto3
import os

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
REGION = os.getenv("AWS_REGION", "us-east-1")

s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION
)

def upload_file_to_s3(file_obj, object_name):
    if not BUCKET_NAME:
        return False
    try:
        s3.upload_fileobj(file_obj, BUCKET_NAME, object_name)
        return True
    except Exception as e:
        print(f"Erro no S3: {e}")
        return False

def download_file_from_s3(object_name, file_path):
    if not BUCKET_NAME:
        return False
    try:
        s3.download_file(BUCKET_NAME, object_name, file_path)
        return True
    except Exception as e:
        print(f"Erro download S3: {e}")
        return False