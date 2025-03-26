import os
import boto3
from boto3.dynamodb.conditions import Attr
from collections import Counter
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
    response = api_compute_statistics(lambda_event_object, orders_table)
    return response


def api_compute_statistics(lambda_event_object, orders_table):
    # Query the GSI 1 of the table and count the number of orders per PK
    query_response = orders_table.table.scan(
        IndexName="GSI1",
        Select="SPECIFIC_ATTRIBUTES",
        ProjectionExpression="#pk,#sk",
        ExpressionAttributeNames={"#pk": "GSI1-PK", "#sk": "GSI1-SK"},
        FilterExpression=Attr("entityType").eq("order"),
    )
    # Compute the average number of orders per shop
    orders_count = Counter(item["GSI1-PK"] for item in query_response["Items"])
    average_orders_per_shop = sum(orders_count.values()) / len(orders_count)
    logger.info(orders_count)
    # Scan the GSI2 of the table to get the number of customers and orders per customer
    query_response = orders_table.table.scan(
        IndexName="GSI2",
        Select="SPECIFIC_ATTRIBUTES",
        ProjectionExpression="#pk,#sk",
        ExpressionAttributeNames={"#pk": "GSI2-PK", "#sk": "GSI2-SK"},
        FilterExpression=Attr("entityType").eq("order"),
    )
    # Compute the average number of orders per customer
    customers_count = Counter(item["GSI2-PK"] for item in query_response["Items"])
    average_orders_per_customer = sum(customers_count.values()) / len(customers_count)
    logger.info(customers_count)
    stats_response = {
        "totalNumberOfShops": len(orders_count),
        "averageNumberOfOrdersPerShop": average_orders_per_shop,
        "totalNumberOfCustomers": len(customers_count),
        "averageNumberOfOrdersPerCustomer": average_orders_per_customer,
    }
    return build_api_response(200, stats_response, CORS_ORIGIN)
