import boto3
import os
import json
from .conftest import FakeLambdaEvent
from dynamodb_helpers import DynamodbTestOrdersData
from moto import mock_aws

TABLE_NAME = os.environ.get("TABLE_NAME")


@mock_aws
def test_list_products_wrong_token():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()

    lambda_event_object = FakeLambdaEvent(
        querystring_params={
            "shopId": "0001",
            "shopToken": "ABC123",  # once in the lifetime of the universe this is going to be the right token. Sorry.
        },
    )

    from lambdas.list_products.main import api_list_shop_products

    api_response = api_list_shop_products(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 401


@mock_aws
def test_list_products_good_token():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()

    shop_id = "0001"
    shop_data = fake_table.get_shop_by_id(shop_id)
    shop_token = shop_data["shopToken"]

    lambda_event_object = FakeLambdaEvent(
        querystring_params={
            "shopId": shop_id,
            "shopToken": shop_token,
        },
    )

    from lambdas.list_products.main import api_list_shop_products

    api_response = api_list_shop_products(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 200
    body = json.loads(api_response["body"])
    # There are 2 products per shop in the test data
    assert len(body["productsList"]) == 2
