import boto3
import os
import uuid
from .conftest import FakeLambdaEvent
from dynamodb_helpers import DynamodbTestOrdersData
from moto import mock_aws

TABLE_NAME = os.environ.get("TABLE_NAME")


@mock_aws
def test_api_place_order_without_shop_token():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    shop_nb = 1
    product_nb = 1
    current_region = boto3.session.Session().region_name
    lambda_event_object = FakeLambdaEvent(
        request_identity={
            "cognitoIdentityPoolId": uuid.uuid4(),
            "cognitoIdentityId": f"{current_region}:{uuid.uuid4()}",
            "cognitoAuthenticationType": "unauthenticated",
            "cognitoAuthenticationProvider": None,
        },
        body={
            "shopId": f"000{shop_nb}",
            "phoneNumber": "0771112233",
            "name": "John Doe",
            "items": [
                {
                    "productId": f"00{shop_nb}{product_nb}",
                    "quantity": 1,
                }
            ],
        },
    )

    from lambdas.place_order.main import api_place_order

    api_response = api_place_order(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 400


@mock_aws
def test_api_place_order_wrong_token():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    shop_nb = 1
    product_nb = 1
    current_region = boto3.session.Session().region_name
    lambda_event_object = FakeLambdaEvent(
        request_identity={
            "cognitoIdentityPoolId": uuid.uuid4(),
            "cognitoIdentityId": f"{current_region}:{uuid.uuid4()}",
            "cognitoAuthenticationType": "unauthenticated",
            "cognitoAuthenticationProvider": None,
        },
        body={
            "shopId": f"000{shop_nb}",
            "phoneNumber": "0771112233",
            "name": "John Doe",
            "items": [
                {
                    "productId": f"00{shop_nb}{product_nb}",
                    "quantity": 1,
                }
            ],
        },
        querystring_params={"shopToken": "wrong_token"},
    )

    from lambdas.place_order.main import api_place_order

    api_response = api_place_order(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 401


@mock_aws
def test_api_place_order_happy_path():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    shop_nb = 1
    product_nb = 1
    shop_id = f"000{shop_nb}"
    shop_data = fake_table.get_shop_by_id(shop_id)
    shop_token = shop_data["shopToken"]
    current_region = boto3.session.Session().region_name
    lambda_event_object = FakeLambdaEvent(
        request_identity={
            "cognitoIdentityPoolId": uuid.uuid4(),
            "cognitoIdentityId": f"{current_region}:{uuid.uuid4()}",
            "cognitoAuthenticationType": "unauthenticated",
            "cognitoAuthenticationProvider": None,
        },
        body={
            "shopId": shop_id,
            "phoneNumber": "0771112233",
            "name": "John Doe",
            "items": [
                {
                    "productId": f"00{shop_nb}{product_nb}",
                    "quantity": 1,
                }
            ],
        },
        querystring_params={"shopToken": shop_token},
    )

    from lambdas.place_order.main import api_place_order

    api_response = api_place_order(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 200
