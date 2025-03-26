import os
import json

import boto3

from dynamodb_helpers import DynamodbTestOrdersData
from moto import mock_aws

from .conftest import FakeLambdaEvent


TABLE_NAME = os.environ.get("TABLE_NAME")


@mock_aws
def test_api_order_id_get_non_existing():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    lambda_event_object = FakeLambdaEvent(
        path_params={"id": "1111"},
    )

    from lambdas.get_shop.main import api_get_shop

    api_response = api_get_shop(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 404


@mock_aws
def test_api_order_id_get_existing():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    lambda_event_object = FakeLambdaEvent(
        path_params={"id": "0001"},
    )

    from lambdas.get_shop.main import api_get_shop

    api_response = api_get_shop(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 200
    response_data = json.loads(api_response["body"])
    assert response_data["shopId"] == "0001"


@mock_aws
def test_list_shops():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()

    shop_list = fake_table.list_shops()
    assert len(shop_list) > 0
