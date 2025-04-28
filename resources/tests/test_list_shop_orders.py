import boto3
import json
import os
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

    from lambdas.list_shop_orders.main import api_list_shop_orders

    api_response = api_list_shop_orders(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 200
    body = json.loads(api_response["body"])
    # There are 2 orders per shop in the test data
    assert len(body["ordersList"]) == 2
