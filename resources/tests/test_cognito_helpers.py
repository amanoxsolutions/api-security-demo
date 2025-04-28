import boto3
import secrets
import string

from cognito_helpers import AppUser
from moto import mock_aws
from collections import namedtuple


CognitoSetup = namedtuple(
    "CognitoSetup",
    ["user_pool_id", "user_pool_client_id", "sub", "password", "identity_pool_id"],
)


def setup_cognito(cognito_idp_client, cognito_identity_client):
    # Setup the Cognito User Pool with 1 test user
    user_pool = cognito_idp_client.create_user_pool(
        PoolName="TestUserPool",
        Policies={
            "PasswordPolicy": {
                "MinimumLength": 8,
                "RequireLowercase": False,
                "RequireNumbers": False,
                "RequireSymbols": False,
                "RequireUppercase": False,
            }
        },
        AutoVerifiedAttributes=["email"],
        AliasAttributes=["email"],
        UsernameAttributes=["email"],
        AdminCreateUserConfig={"AllowAdminCreateUserOnly": False},
        Schema=[
            {
                "Name": "role",
                "AttributeDataType": "String",
                "Mutable": True,
                "Required": False,
            },
            {
                "Name": "shopId",
                "AttributeDataType": "String",
                "Mutable": True,
                "Required": False,
            },
        ],
    )["UserPool"]
    user_pool_id = user_pool["Id"]
    user_pool_provider_name = user_pool["Name"]
    user_pool_client_id = cognito_idp_client.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName="TestClient",
        GenerateSecret=False,
        ExplicitAuthFlows=["USER_PASSWORD_AUTH"],
    )["UserPoolClient"]["ClientId"]
    username = cognito_idp_client.admin_create_user(
        UserPoolId=user_pool_id,
        Username="test@example.com",
        UserAttributes=[
            {"Name": "email", "Value": "test@example.com"},
            {"Name": "email_verified", "Value": "true"},
            {"Name": "phone_number", "Value": "+41111111111"},
            {"Name": "phone_number_verified", "Value": "true"},
            {"Name": "custom:role", "Value": "customer"},
        ],
        MessageAction="SUPPRESS",
    )["User"]["Username"]
    securechars = string.ascii_letters + string.digits + string.punctuation
    password = "".join(secrets.choice(securechars) for i in range(8))
    cognito_idp_client.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=username,
        Password=password,
        Permanent=True,
    )
    # Cognito Identity Pool
    identity_pool_id = cognito_identity_client.create_identity_pool(
        IdentityPoolName="TestIdentityPool",
        AllowUnauthenticatedIdentities=True,
        CognitoIdentityProviders=[
            {
                "ClientId": user_pool_client_id,
                "ProviderName": user_pool_provider_name,
            }
        ],
    )["IdentityPoolId"]
    return CognitoSetup(
        user_pool_id, user_pool_client_id, username, password, identity_pool_id
    )


@mock_aws
def test_unauthenticated_user():
    cognito_idp_client = boto3.client("cognito-idp", region_name="eu-west-1")
    cognito_identity_client = boto3.client("cognito-identity", region_name="eu-west-1")
    cognito_setup = setup_cognito(cognito_idp_client, cognito_identity_client)
    identity_id = cognito_identity_client.get_id(
        IdentityPoolId=cognito_setup.identity_pool_id
    )["IdentityId"].split(":")[-1]
    current_region = boto3.session.Session().region_name
    request_identity = {
        "cognitoIdentityPoolId": cognito_setup.identity_pool_id,
        "cognitoIdentityId": f"{current_region}:{identity_id}",
        "cognitoAuthenticationType": "unauthenticated",
        "cognitoAuthenticationProvider": None,
    }
    user = AppUser(request_identity)
    assert user.sub is None
    assert user.id == identity_id
    assert user.type == "visitor"
    assert user.attributes == {}


@mock_aws
def test_authenticated_user():
    cognito_idp_client = boto3.client("cognito-idp")
    cognito_identity_client = boto3.client("cognito-identity")
    cognito_setup = setup_cognito(cognito_idp_client, cognito_identity_client)
    id_token = cognito_idp_client.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={
            "USERNAME": cognito_setup.sub,
            "PASSWORD": cognito_setup.password,
        },
        ClientId=cognito_setup.user_pool_client_id,
    )["AuthenticationResult"]["IdToken"]
    identity_id = cognito_identity_client.get_id(
        IdentityPoolId=cognito_setup.identity_pool_id,
        Logins={
            f"cognito-idp.eu-west-1.amazonaws.com/{cognito_setup.user_pool_id}": id_token
        },
    )["IdentityId"]
    request_identity = {
        "cognitoIdentityPoolId": cognito_setup.identity_pool_id,
        "cognitoIdentityId": identity_id,
        "cognitoAuthenticationType": "authenticated",
        "cognitoAuthenticationProvider": f"cognito-idp.eu-west-1.amazonaws.com/{cognito_setup.user_pool_id},cognito-idp.eu-west-1.amazonaws.com/{cognito_setup.user_pool_id}:CognitoSignIn:{cognito_setup.sub}",
    }
    user = AppUser(request_identity, cognito_setup.user_pool_id)
    assert user.sub == cognito_setup.sub
    assert user.id == cognito_setup.sub
    assert user.type == "registered_user"
    assert user.attributes["custom:role"] == "customer"
