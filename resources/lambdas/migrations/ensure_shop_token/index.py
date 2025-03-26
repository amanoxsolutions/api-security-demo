import os
import boto3
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from dynamodb_helpers import DynamodbTestOrdersData
from log_helpers import CustomLogger

logger = CustomLogger()
tracer = Tracer()
ddb = boto3.resource("dynamodb")

TABLE_NAME = os.environ.get("TABLE_NAME")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler(capture_response=False)
def lambda_handler(event: dict, context: LambdaContext):
    orders_table = DynamodbTestOrdersData(
        TABLE_NAME, dynamodb_resource=ddb, logger=logger
    )
    ensure_shop_token(orders_table)


def ensure_shop_token(orders_table):
    shops = orders_table.list_shops()
    for shop in shops:
        if not shop.get("shopToken"):
            logger.info(
                f"Regenerating token for shop {shop['shopId']} {shop.get('name')}"
            )
            orders_table.regenerate_shop_token(shop["shopId"])
        else:
            logger.info(
                f"Shop {shop['shopId']} {shop.get('name')} already has a token: {shop['shopToken']}"
            )
