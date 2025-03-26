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
        querystring_params={"shopId": "0001"},
    )

    from lambdas.get_service_stats.main import api_compute_statistics

    api_response = api_compute_statistics(lambda_event_object, fake_table)
    assert api_response["statusCode"] == 200
    body = json.loads(api_response["body"])
    # There are 2 shops in the test data
    assert body["totalNumberOfShops"] == 2
    # There are 2 orders per shop
    assert body["averageNumberOfOrdersPerShop"] == 2.0
    # There are 4 customers in the test data
    assert body["totalNumberOfCustomers"] == 2
    # There are 1 order per each customer
    assert body["averageNumberOfOrdersPerCustomer"] == 2.0
