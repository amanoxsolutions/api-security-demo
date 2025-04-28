import os
import boto3
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from api_helpers import LambdaEvent, validate_method, build_api_response
from dynamodb_helpers import DynamodbTestOrdersData, ShopDoesNotExist
from log_helpers import CustomLogger

logger = CustomLogger()
tracer = Tracer()
ddb = boto3.resource("dynamodb")

CORS_ORIGIN = os.environ.get("CORS_ORIGIN")
TABLE_NAME = os.environ.get("TABLE_NAME")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler(capture_response=False)
@validate_method("POST", logger)
def lambda_handler(event: dict, context: LambdaContext):
    lambda_event_object = LambdaEvent(event)
    orders_table = DynamodbTestOrdersData(
        TABLE_NAME, dynamodb_resource=ddb, logger=logger
    )
    response = api_regenerate_shop_token(lambda_event_object, orders_table)
    return response


def api_regenerate_shop_token(lambda_event_object, orders_table):
    shop_id = lambda_event_object.pathparameters["id"]
    try:
        new_token = orders_table.regenerate_shop_token(shop_id)
    except ShopDoesNotExist:
        return build_api_response(404, {"error": "Shop does not exist"}, CORS_ORIGIN)
    return build_api_response(204, {"shopToken": new_token}, CORS_ORIGIN)
