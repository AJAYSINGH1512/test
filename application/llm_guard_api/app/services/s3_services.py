from idlelib.iomenu import errors

import boto3
import os 
from dotenv import load_dotenv, find_dotenv
import shutil

load_dotenv(find_dotenv())
aws_access_key_id = os.getenv('aws_access_key')
aws_secret_access_key = os.getenv('aws_secret_key')
region_name = os.getenv('aws_region')
bucket_name = os.getenv('bucket_name')

s3 = boto3.client(
    's3',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
)

def upload_folder_s3(local_folder,bucket,s3_folder):
    if not s3_folder.endswith('/'):
        s3_folder += '/'

    for root,_,files in os.walk(local_folder):
        for file in files:
            local_file_path = os.path.join(root,file)
            relative_path = os.path.relpath(local_file_path,local_folder)
            s3_key = os.path.join(s3_folder,relative_path).replace("\\","/")
            try:
                s3.upload_file(local_file_path,bucket,s3_key)
                print(f"uploaded: {local_file_path} -> s3://{bucket}/{s3_key}")
            except Exception as e:
                print(f"Error uploading {local_file_path}:{e}")

    return 

def upload_file_s3(file_name,bucket,object_name):
    print("Ssssssssssssssssssssssssssss")
    print("ssssssssssssssssssss",[file_name,object_name])
    object_name = object_name.replace("\\","/")
    if object_name is None:
        object_name = os.path.basename(file_name)
    try:
        s3.upload_file(file_name,bucket,object_name)
        return f"{file_name} is uploaded successfully"
    except Exception as e:
        return f"Unexpected error occured. {e}"

def download_file_s3(bucket,object_name):
    try:
        response = s3.get_object(Bucket = bucket,Key=object_name)
        op = response["Body"].read().decode("utf-8",errors="ignore")
        return op
    except Exception as e:
        print(str(e))
        return f"Unexpected error occured. {e}"

def download_file_s3_base64(bucket,object_name):
    try:
        response = s3.get_object(Bucket = bucket,Key=object_name)
        op = response["Body"].read()
        return op
    except Exception as e:
        return f"Unexpected error occured. {e}"

def list_files_s3(bucket,prefix=""):
    try:
        response = s3.list_objects_v2(Bucket=bucket,Prefix=prefix)
        if 'Contents' in response:
            files = [obj['Key'] for obj in response['Contents']]
            return files
        else:
            print("No files found")
            return []
    except Exception as e:
        return f"Unexpected error occured. {e}"

def delete_file_s3(bucket,object_name):
    try:
        s3.delete_object(Bucket=bucket,Key=object_name)
        return f"{object_name} deleted successfully."
    except Exception as e:
        return f"Unexpected error occured. {e}"

def delete_folder_s3(bucket,folder_name):

    if not folder_name.endswith('/'):
        folder_name += "/"
    try:
        paginator = s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket,Prefix=folder_name)
        objects_to_delete = []
        for page in pages:
            if "Contents" in page:
                objects_to_delete.extend([{"Key":obj["Key"]} for obj in page['Contents']])
        if 'Contents' in objects_to_delete:
            delete_keys = [{'Key':obj['Key']} for obj in objects_to_delete['Contents']]
            s3.delete_objects(Bucket=bucket, Delete = {"Objects":- delete_keys})
            return f"{folder_name} is deleted successfully"
        else:
            return f"{folder_name} is already empty"

    except Exception as e:
        return f"Unexpected error occured. {e}"


def delete_folder(folder_path):
    if os.path.isdir(folder_path):
        shutil.rmtree(folder_path)
        return "Folder deleted successfully."
    else:
        return "No folder exists."


def delete_file(file_path):
    if os.path.isfile(file_path):
        os.remove(file_path)
        return "File deleted successfully."
    else:
        return "No file exists."


import base64
def encode_file_to_base(content):
    content = str(content)
    try:
        content = content.encode("utf-8")
        return base64.b64encode(content).decode("utf-8") 
    except Exception as e:
        return f"Unexpected Error Occured {e}"

def process_folder(file_dict):
    file_tree = {}

    # for file_dict in file_dict_list:
    for file_path,base64_content in file_dict.items():
        parts = file_path.split("/")
        current_level = file_tree

        for part in parts[:-1]:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]

        current_level[parts[-1]] = base64_content
    return file_tree    

def generate_json(task_id,emp_id):
    folder_path_s3 = f"Output_artifacts/{emp_id}/CE_Agent/{task_id}"
    result = {}
    files_list = list_files_s3(bucket=bucket_name,prefix=folder_path_s3)
    for i in files_list:
        new_path = f"Output_artifacts/{emp_id}/CE_Agent/{task_id}/"
        output_file_path = i.replace(new_path,"")
        content = download_file_s3(bucket=bucket_name,object_name=i)
        final_content = encode_file_to_base(content)
        result[output_file_path] = final_content
    final_result = process_folder(result)
    return final_result