import json
import os
from api_helpers import LambdaEvent


os.environ["CORS_ORIGIN"] = "mock_cors_origin"
os.environ["TABLE_NAME"] = "mock_table"
os.environ["AWS_DEFAULT_REGION"] = "eu-west-1"


class FakeLambdaEvent(LambdaEvent):
    def __init__(
        self,
        *,
        path_params: dict = None,
        querystring_params: dict = None,
        request_identity: dict = None,
        body: dict = None,
    ):
        if path_params is None:
            path_params = {}
        if querystring_params is None:
            querystring_params = {}
        if body is None:
            body_params = ""
        else:
            body_params = json.dumps(body)
        self.querystring = querystring_params
        self.pathparameters = path_params
        self.requestidentity = request_identity
        self.body = body_params
