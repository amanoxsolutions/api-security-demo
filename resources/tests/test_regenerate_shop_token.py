import os
import json

import boto3

from dynamodb_helpers import DynamodbTestOrdersData
from moto import mock_aws

from .conftest import FakeLambdaEvent


TABLE_NAME = os.environ.get("TABLE_NAME")


@mock_aws
def test_regenerate_shop_token():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    lambda_event_object = FakeLambdaEvent(
        path_params={"id": "0001"},
    )

    from lambdas.regenerate_shop_token.main import api_regenerate_shop_token

    api_response = api_regenerate_shop_token(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 204
    response_data = json.loads(api_response["body"])
    assert type(response_data.get("shopToken")) is str


@mock_aws
def test_regenerate_shop_token_non_existing():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    lambda_event_object = FakeLambdaEvent(
        path_params={"id": "1111"},
    )

    from lambdas.regenerate_shop_token.main import api_regenerate_shop_token

    api_response = api_regenerate_shop_token(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 404


@mock_aws
def test_regenerate_shop_token_lifecycle():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    lambda_event_object = FakeLambdaEvent(
        path_params={"id": "0001"},
    )

    from lambdas.get_shop.main import api_get_shop
    from lambdas.regenerate_shop_token.main import api_regenerate_shop_token

    # First time we already have shop data including the token
    shop_response1 = api_get_shop(lambda_event_object, fake_table)
    shop_response1_data = json.loads(shop_response1["body"])
    token = shop_response1_data["shopToken"]

    # Regenerate the token: we should get a different one
    regenerate_response1 = api_regenerate_shop_token(lambda_event_object, fake_table)
    regenerate_response1_data = json.loads(regenerate_response1["body"])
    token1 = regenerate_response1_data["shopToken"]
    assert token != token1

    # Regenerate the token again: we should get a different one
    regenerate_response2 = api_regenerate_shop_token(lambda_event_object, fake_table)
    regenerate_response2_data = json.loads(regenerate_response2["body"])
    token2 = regenerate_response2_data["shopToken"]
    assert token1 != token2


@mock_aws
def test_ensure_shop_token():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()

    new_shop = fake_table.create_shop_data(shop_id="1111")
    fake_table.table.put_item(Item=new_shop)

    shop_from_the_table = fake_table.get_shop_by_id("1111")
    assert "shopToken" not in shop_from_the_table

    from lambdas.migrations.ensure_shop_token.index import ensure_shop_token

    ensure_shop_token(fake_table)

    shop_list2 = fake_table.list_shops()
    for shop in shop_list2:
        assert type(shop["shopToken"]) is str
