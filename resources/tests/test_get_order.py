import boto3
import os
import uuid
from .conftest import FakeLambdaEvent
from dynamodb_helpers import DynamodbTestOrdersData
from moto import mock_aws

TABLE_NAME = os.environ.get("TABLE_NAME")


@mock_aws
def test_api_order_id_get_different_user():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    current_region = boto3.session.Session().region_name
    lambda_event_object = FakeLambdaEvent(
        path_params={"id": "1111"},
        request_identity={
            "cognitoIdentityPoolId": uuid.uuid4(),
            "cognitoIdentityId": f"{current_region}:{uuid.uuid4()}",
            "cognitoAuthenticationType": "unauthenticated",
            "cognitoAuthenticationProvider": None,
        },
    )

    from lambdas.get_order.main import api_get_order

    api_response = api_get_order(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 401


@mock_aws
def test_api_order_id_get_same_user():
    ddb = boto3.resource("dynamodb", region_name="eu-west-1")
    fake_table = DynamodbTestOrdersData(TABLE_NAME, ddb)
    fake_table.prefill_table_with_testdata()
    # Get the first order from the test data
    order = fake_table.get_order_data("1111")
    current_region = boto3.session.Session().region_name
    cognito_identity_id = order["customerId"]
    lambda_event_object = FakeLambdaEvent(
        path_params={"id": "1111"},
        request_identity={
            "cognitoIdentityPoolId": uuid.uuid4(),
            "cognitoIdentityId": f"{current_region}:{cognito_identity_id}",
            "cognitoAuthenticationType": "unauthenticated",
            "cognitoAuthenticationProvider": None,
        },
    )

    from lambdas.get_order.main import api_get_order

    api_response = api_get_order(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 200
