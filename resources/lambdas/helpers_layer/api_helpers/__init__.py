import json
import decimal
from functools import wraps


class LambdaEvent:
    """
    Class that represents an event to the translation backend

    Args:
        event (dict): The lambda event
    """

    def __init__(self, event: dict):
        self.body: str = event["body"]
        self.method: str = event["httpMethod"]
        self.path: str = event["path"]
        self.resource: str = event["resource"]

        self.signature: str = ""
        if event["headers"] is not None:
            self.signature = event["headers"].get("x-caller-signature", "")

        self.querystring: dict = event["queryStringParameters"]
        if self.querystring is None:
            self.querystring = {}

        self.pathparameters: dict = event["pathParameters"]
        if self.pathparameters is None:
            self.pathparameters = {}

        self.headers = event.get("headers")
        if self.headers is None:
            self.headers = {}

        self.authorizerclaims: dict = (
            event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        )

        self.requestidentity: dict = event.get("requestContext", {}).get("identity", {})

        self.bearer_token: str = self.headers.get("Authorization")

    def is_conformant(self) -> tuple[bool, str]:
        """
        Checks if the event payload is compatible with the lambda purpose

        Returns:
            tuple[result:bool, reason:str]: result: True if the event payload is conformant.
                                            reason: describes the reasons for (non) conformity
        """
        if self.method not in ["POST", "PUT"]:
            return True, "OK"
        if self.body is None:
            return False, f"Error: {self.method} method with empty body"
        try:
            parsed_body = json.loads(self.body)
        except json.decoder.JSONDecodeError:
            return False, "Error: body wasn't a valid JSON"
        if {"componentMeasurement", "timestamp", "data"}.issubset(parsed_body.keys()):
            return True, "OK"
        return False, "Missing required parameters in body"

    def is_access_token(self) -> bool:
        """
        Checks if the Bearer token is an access token.
        """
        return self.authorizerclaims.get("token_use") == "access"

    def is_id_token(self) -> bool:
        """
        Checks if the Bearer token is an id token.
        """
        return self.authorizerclaims.get("token_use") == "id"

    def is_proper_order(self) -> bool:
        """
        Checks if the event is a proper order
        """
        try:
            parsed_body = json.loads(self.body)
            if {"shopId", "phoneNumber", "name", "items"}.issubset(parsed_body.keys()):
                return True
        except json.decoder.JSONDecodeError:
            return False, "Error: body wasn't a valid JSON"


# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, value):
        if isinstance(value, decimal.Decimal):
            if value % 1 > 0:
                return float(value)
            else:
                return int(value)
        return super(DecimalEncoder, self).default(value)


def validate_method(allowed_methods: str | list[str], logger, cors_origin="*"):
    """
    Relies on the arguments of a lambda handler being (event, context).
    If the method is not allowed, returns a 400 error response.
    """

    if isinstance(allowed_methods, str):
        allowed_methods = [allowed_methods]

    def decorator(lambda_handler_func):
        @wraps(lambda_handler_func)
        def wrapper(event, context):
            lambda_event_object = LambdaEvent(event)
            if lambda_event_object.method not in allowed_methods:
                error_message = f"{lambda_event_object.method} method is not implemented here. Allowed methods: {allowed_methods}"
                logger.error({"type": "error", "data": error_message})
                return build_api_response(
                    400, {"message": "ERROR : " + error_message}, cors_origin
                )
            return lambda_handler_func(event, context)

        return wrapper

    return decorator


def build_api_response(code: int, body: dict, cors_origin="*") -> dict:
    """Builds a standardized response and returns it

    Args:
        code (int): The HTTP code for the response
        body (dict): A dict variable to be sent as the Body of response

    Returns:
        dict: The response to be sent
    """
    response = {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "GET,OPTIONS,POST,PUT",
            "Access-Control-Allow-Origin": cors_origin,
        },
        "body": json.dumps(body, cls=DecimalEncoder, sort_keys=True),
    }

    return response
