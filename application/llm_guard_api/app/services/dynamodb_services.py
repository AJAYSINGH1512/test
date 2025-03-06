import boto3
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv, find_dotenv
import os
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr


load_dotenv(find_dotenv())
aws_access_key_id = os.environ.get('aws_access_key')
aws_secret_access_key = os.environ.get('aws_secret_key')
region_name = os.environ.get('aws_region')
agenticAI_task_master = os.environ.get('agenticAI_task_master')
agenticAI_task_exception = os.environ.get('agenticAI_task_exception')

dynamodb = boto3.resource(
    'dynamodb',
    region_name=region_name,
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
)

dynamodb_client = boto3.client('dynamodb',
                               aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
    )


master_task_sheet = dynamodb.Table('agenticAI_task_master')
task_exception = dynamodb.Table(agenticAI_task_exception)

def add_task(task_id,status,submitted_by,task_type):
    response = master_task_sheet.put_item(
        Item = {
            "Task_Id": task_id,
            "Current_Status": status,
            "Date": datetime.now().strftime('%m-%d-%Y %I:%M:%S %p'),
            "Submitted_By": submitted_by,
            "Task_Type":task_type
        }
    )
    return response

def get_task(task_id):
    result = master_task_sheet.get_item(Key = {"Task_Id":task_id})
    task = result.get("Item")
    return task

def update_task(task_id,new_status):
    response = master_task_sheet.update_item(
        Key = {"Task_Id":task_id},
        UpdateExpression = "SET Current_Status = :s",
        ExpressionAttributeValues={":s":new_status},
        ReturnValues = "UPDATED_NEW",

    )
    result = get_task(task_id=task_id)
    return result


def delete_task(task_id):
    response = master_task_sheet.delete_item(Key={"Task_Id":task_id})
    return response

def add_exception(task_id,expt,submitted_by,task_type):
    response = task_exception.put_item(
        Item = {
            "Task_Id": task_id,
            "Task_Exception": expt,
            "Date": datetime.now().strftime('%m-%d-%Y %I:%M:%S %p'),
            "Submitted_By": submitted_by,
            "Task_Type":task_type
        }
    )
    return response

def get_gsi_names():
    try:
        response = dynamodb_client.describe_table(TableName= agenticAI_task_master)
        indexes = response.get("Table",{}).get("GlobalSecondaryIndexes",[])
        return [index["IndexName"] for index in indexes]
    except ClientError as e:
        print(f"Error fetching GSI names: {e}")
        return []

def get_multiple_tasks(task_type,submitted_by):
    response = master_task_sheet.scan(FilterExpression = Attr('Task_Type').eq(task_type) & Attr('Submitted_By').eq(submitted_by))
    items = response["Items"]
    return items