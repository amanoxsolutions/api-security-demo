import boto3
import os
import json
from .conftest import FakeLambdaEvent
from dynamodb_helpers import DynamodbTestOrdersData
from moto import mock_aws

TABLE_NAME = os.environ.get("TABLE_NAME")


@mock_aws
def test_api_order_id_get():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    lambda_event_object = FakeLambdaEvent(
        path_params={"id": "0001"},
    )

    from lambdas.get_shop_sales.main import api_get_shop_total_sales

    api_response = api_get_shop_total_sales(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 200
    body = json.loads(api_response["body"])
    # There are 2 orders per shop in the test data. The orders for the first shops have an amount of 110 and 120
    assert body["totalAmount"] == 350
