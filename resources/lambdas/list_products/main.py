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


@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler(capture_response=False)
@validate_method("GET", logger)
def lambda_handler(event: dict, context: LambdaContext):
    lambda_event_object = LambdaEvent(event)
    orders_table = DynamodbTestOrdersData(
        TABLE_NAME, dynamodb_resource=ddb, logger=logger
    )
    response = api_list_shop_products(lambda_event_object, orders_table)
    return response


def api_list_shop_products(lambda_event_object, orders_table):
    try:
        shop_id = lambda_event_object.querystring["shopId"]
        shop_token = lambda_event_object.querystring["shopToken"]
    except KeyError:
        return build_api_response(
            400, {"message": "Missing shopId or shopToken"}, CORS_ORIGIN
        )

    shop_data = orders_table.get_shop_by_id(shop_id)
    if shop_data is None:
        return build_api_response(404, {"message": "Shop not found"}, CORS_ORIGIN)

    if shop_data["shopToken"] != shop_token:
        return build_api_response(
            401,
            {"message": "Unauthorized this is not the Token we hanged at the door"},
            CORS_ORIGIN,
        )

    products_list = orders_table.list_products_by_shop_id(shop_id)
    response_object = {"shopId": shop_id, "productsList": products_list}
    logger.info(response_object)
    return build_api_response(200, response_object, CORS_ORIGIN)
