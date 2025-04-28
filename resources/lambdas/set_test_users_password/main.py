import os
import boto3
import json
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from crhelper import CfnResource

helper = CfnResource()
logger = Logger()
cognito_idp = boto3.client("cognito-idp")
asm = boto3.client("secretsmanager")

USER_POOL_ID = os.environ["USER_POOL_ID"]
USERS = os.environ["USERS"].split(",")
USER_PASSWORD_SECRET_ARN = os.environ["USER_PASSWORD_SECRET_ARN"]


@logger.inject_lambda_context()
def lambda_handler(event: dict, context: LambdaContext):
    helper(event, context)


@helper.create
def create(_, __):
    # Get the user password from the secret in Secrets Manager
    try:
        secret = asm.get_secret_value(SecretId=USER_PASSWORD_SECRET_ARN)["SecretString"]
        user_password = json.loads(secret)["password"]
        logger.info("User password retrieved from Secrets Manager")
    except ClientError as e:
        logger.exception("Failed to get user password from Secrets Manager", e)
        raise e
    # Set the password to all users in the pool
    for user in USERS:
        try:
            cognito_idp.admin_set_user_password(
                UserPoolId=USER_POOL_ID,
                Username=user,
                Password=user_password,
                Permanent=True,
            )
            logger.info(f"Password set for user {user}")
        except ClientError as e:
            logger.exception(f"Failed to set password for user {user}", e)
            raise e


@helper.update
@helper.delete
def do_nothing(_, __):
    logger.info("Nothing to do")
