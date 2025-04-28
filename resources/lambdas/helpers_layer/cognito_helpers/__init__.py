import boto3
from log_helpers import ensure_logger


class AppUser:
    """
    Class that represents an app user. The user can either be
    * an authenticated user from the Cognito User Pool
    * or a guest user from the Cognito Identity Pool

    An authenticated user has the following attributes:
    * sub is the Cognito User Pool SUB
    * id is the sub
    * type is "registered_user"
    * attributes is a dict with the user attributes from the Cognito User Pool

    A guest user has the following attributes:
    * sub is None
    * id is the Cognito Identity Pool ID
    * type is "visitor"
    * attributes is an empty dict

    Args:
        request_identity (dict): The requestContext.identity object from the lambda event
        user_pool_id (str): The Cognito User Pool ID
    """

    def __init__(self, request_identity: dict, user_pool_id: str = None, logger=None):
        self.user_pool_id = user_pool_id
        self.identity_pool_id = request_identity.get("cognitoIdentityPoolId")
        self.identity_id = request_identity.get("cognitoIdentityId")
        self.authenticated_type = request_identity.get("cognitoAuthenticationType")
        # If cognitoAuthenticationProvider has a value, we get the Cogntio User Pool SUB from it as the last element when slicing with ":"
        # The id is set to the SUB if it exists otherwise the id is set to the identity_id
        self.sub = (
            request_identity.get("cognitoAuthenticationProvider").split(":")[-1]
            if request_identity.get("cognitoAuthenticationProvider")
            else None
        )
        self.id = self.sub if self.sub else self.identity_id.split(":")[-1]
        # The user type is set to "registered_user" if the authenticated_type=authenticated, otherwise it is set to "visitor"
        self.type = (
            "registered_user"
            if self.authenticated_type == "authenticated"
            else "visitor"
        )
        self.attributes = self._get_user_attributes()
        self.logger = ensure_logger(logger)

    def _cognito_attributes_as_dict(self, attribute_list: list[dict]) -> dict:
        """
        Transform a list of cognito attributes like [{"Name": "sub", "Value": "1234"}, ...] into a dict like {"sub": "1234", ...}
        """
        return {attribute["Name"]: attribute["Value"] for attribute in attribute_list}

    def _get_user_attributes(self) -> dict:
        """Get the user data from the cognito pool and returns it as a dict"""
        if not self.sub:
            # The user is not an authenticated user
            return {}
        if not self.user_pool_id:
            # The user is an authenticated user but the user_pool_id is not set
            raise ValueError("user_pool_id is not set")
        try:
            cognito_idp_client = boto3.client("cognito-idp")
            cognito_user = cognito_idp_client.admin_get_user(
                UserPoolId=self.user_pool_id, Username=self.sub
            )

            user_attributes = self._cognito_attributes_as_dict(
                cognito_user.get("UserAttributes")
            )
            return user_attributes
        except Exception as e:
            self.logger.exception(
                f"Failed to get user data for user {self.sub} from cognito", e
            )
            raise e

    def is_customer(self) -> bool:
        """Returns True if the user is a registered customer or a visitor"""
        return self.type == "visitor" or (
            self.type == "registered_user"
            and self.attributes.get("custom:role") == "customer"
        )

    def is_admin(self) -> bool:
        """Returns True if the user is an admin"""
        return (
            self.type == "registered_user"
            and self.attributes.get("custom:role") == "admin"
        )

    def is_shop_owner(self) -> bool:
        """Returns True if the user is a shop owner"""
        return (
            self.type == "registered_user"
            and self.attributes.get("custom:role") == "shop_owner"
        )

    def get_customer_dynamodb_key(self) -> str | None:
        """Returns the ID of the customer formatted for DynamoDB.
        * If the user is a visitor, the key is "v#{id}
        * If the user is a registered user, with the attribute "role" set to "customer" the key is "c#{id}"
        """
        if self.type == "visitor":
            # The Identity pool id is of format <aws region>:<uuid>. We want to keep only the uuid
            return f"v#{self.id}"
        if (
            self.type == "registered_user"
            and self.attributes.get("custom:role") == "customer"
        ):
            return f"c#{self.id}"
        return None
