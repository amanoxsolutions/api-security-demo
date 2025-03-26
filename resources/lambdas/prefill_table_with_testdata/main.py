import os
import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from dynamodb_helpers import DynamodbTestOrdersData
from crhelper import CfnResource

helper = CfnResource()
logger = Logger()
ddb = boto3.resource("dynamodb")
cognito_idp = boto3.client("cognito-idp")

TABLE_NAME = os.environ.get("TABLE_NAME")
COGNITO_USERPOOL_ID = os.environ.get("COGNITO_USERPOOL_ID")


@logger.inject_lambda_context()
def lambda_handler(event: dict, context: LambdaContext):
    helper(event, context)


@helper.create
def create(_, __):
    # Get the SUBs of all the users in the Cognito user pool who have the custom:role
    # attribute set to "customer"
    # Note: no need to use a paginator here to list users since at this stage we only have a handful of
    # test users in the pool
    logger.info("Get the users data from the Cognito user pool")
    all_users = cognito_idp.list_users(UserPoolId=COGNITO_USERPOOL_ID)
    # Filter the users to only those with the custom:role attribute set to "customer"
    # And create a list of customers as a dictionary of {"username": username, "sub": sub, "phone_number": phone_number}
    customer_users = []
    for user in all_users["Users"]:
        # Group attributes by name and create a dict
        attrs = dict(
            (attr["Name"], attr.get("Value", attr.get("Key")))
            for attr in user["Attributes"]
        )
        if attrs.get("custom:role") == "customer":
            customer_users.append(
                {
                    "username": attrs["email"].split("@")[0],
                    "dynamodb_key": f"c#{attrs['sub']}",
                    "phone_number": attrs.get("phone_number"),
                }
            )
    orders_table = DynamodbTestOrdersData(
        TABLE_NAME, dynamodb_resource=ddb, logger=logger
    )
    logger.info("Prefill DynamoDB table with test data.")
    orders_table.prefill_table_with_testdata(test_customers=customer_users)


@helper.update
@helper.delete
def do_nothing(_, __):
    logger.info("Nothing to do")
