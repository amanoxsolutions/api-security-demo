import os
import boto3
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext
from api_helpers import LambdaEvent, validate_method, build_api_response
from dynamodb_helpers import DynamodbTestOrdersData
from cognito_helpers import AppUser
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
    response = api_get_order(lambda_event_object, orders_table)
    return response


def api_get_order(lambda_event_object, orders_table):
    order_id = lambda_event_object.pathparameters.get("id")
    user = AppUser(
        request_identity=lambda_event_object.requestidentity,
        user_pool_id=COGNITO_USER_POOL_ID,
        logger=logger,
    )
    order_data = orders_table.get_order_data(order_id)
    logger.info({"data": {"order_data": order_data}})
    if user.id == order_data.get("customerId") or (
        user.is_shop_owner()
        and user.attributes["custom:shopId"] == order_data["shopId"]
    ):
        return build_api_response(200, order_data, CORS_ORIGIN)
    return build_api_response(401, {"message": "Unauthorized"}, CORS_ORIGIN)
