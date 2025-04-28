import os
import boto3
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from api_helpers import LambdaEvent, validate_method, build_api_response
from dynamodb_helpers import DynamodbTestOrdersData
from log_helpers import CustomLogger

logger = CustomLogger()
tracer = Tracer()
ddb = boto3.resource("dynamodb")

CORS_ORIGIN = os.environ.get("CORS_ORIGIN")
TABLE_NAME = os.environ.get("TABLE_NAME")
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID")


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler(capture_response=False)
@validate_method("GET", logger)
def lambda_handler(event: dict, context: LambdaContext):
    lambda_event_object = LambdaEvent(event)
    orders_table = DynamodbTestOrdersData(
        TABLE_NAME, dynamodb_resource=ddb, logger=logger
    )
    return api_get_shop(lambda_event_object, orders_table)


def api_get_shop(lambda_event_object, orders_table):
    shop_id = lambda_event_object.pathparameters["id"]
    shop_data = orders_table.get_shop_by_id(shop_id)
    logger.info({"shop_data": shop_data})
    if shop_data is None:
        return build_api_response(404, {"message": "Not found"}, CORS_ORIGIN)
    return build_api_response(200, shop_data, CORS_ORIGIN)
