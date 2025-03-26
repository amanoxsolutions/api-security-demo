import json
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
@validate_method("POST", logger)
def lambda_handler(event: dict, context: LambdaContext):
    lambda_event_object = LambdaEvent(event)
    orders_table = DynamodbTestOrdersData(
        TABLE_NAME, dynamodb_resource=ddb, logger=logger
    )
    response = api_place_order(lambda_event_object, orders_table)
    return response


def api_place_order(lambda_event_object, orders_table):
    event_data = json.loads(lambda_event_object.body)
    try:
        shop_token = lambda_event_object.querystring["shopToken"]
    except KeyError:
        return build_api_response(400, {"message": "Missing shopToken"}, CORS_ORIGIN)

    if lambda_event_object.is_proper_order():
        shop_id = event_data["shopId"]
        shop_data = orders_table.get_shop_by_id(shop_id)
        user = AppUser(
            request_identity=lambda_event_object.requestidentity,
            user_pool_id=COGNITO_USER_POOL_ID,
            logger=logger,
        )
        if shop_data["shopToken"] != shop_token:
            return build_api_response(
                401,
                {"message": "Unauthorized this is not the Token we hanged at the door"},
                CORS_ORIGIN,
            )

        try:
            order_id = orders_table.put_new_order(
                shop_id=event_data["shopId"],
                customer_key=user.get_customer_dynamodb_key(),
                phone_number=event_data["phoneNumber"],
                customer_name=event_data["name"],
                items=event_data["items"],
            )
            return build_api_response(200, {"orderId": order_id}, CORS_ORIGIN)
        except Exception:
            return build_api_response(
                400, {"message": "ERROR :  Failed to store order"}, CORS_ORIGIN
            )
    else:
        return build_api_response(
            400, {"message": "ERROR : Invalid order"}, CORS_ORIGIN
        )
