import { Construct } from 'constructs';
import {RemovalPolicy, CustomResource, Duration, Stack} from 'aws-cdk-lib';
import { RetentionDays } from 'aws-cdk-lib/aws-logs';
import { PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';
import { Runtime, Code, SingletonFunction } from 'aws-cdk-lib/aws-lambda';
import {
  UserPool,
  StringAttribute,
  CfnIdentityPool,
  CfnIdentityPoolPrincipalTag,
  CfnIdentityPoolRoleAttachment,
  CfnUserPoolUser
} from 'aws-cdk-lib/aws-cognito';
import {
  Effect,
  Policy,
  PolicyDocument,
  Role,
  IRole,
  ServicePrincipal,
  PolicyStatement,
  FederatedPrincipal
} from "aws-cdk-lib/aws-iam";
import { Secret } from 'aws-cdk-lib/aws-secretsmanager';


export interface CognitoUserPoolUserProps {
  readonly userPoolId: string;
  readonly username: string;
  readonly phoneNumber: string;
  readonly role: string;
  readonly shopId?: string;
}

export class CognitoUserPoolUser extends Construct {
  public readonly userPoolUser: CfnUserPoolUser;

  constructor(scope: Construct, id: string, props: CognitoUserPoolUserProps) {
    super(scope, id);

    //
    // Create Test Cognito Users in the User Pool
    //
    const userEmail = `${props.username.toLowerCase()}@axians.com`;
    const userAttributes = [
      { name: 'email', value: userEmail },
      { name: 'email_verified', value: 'true' },
      { name: 'phone_number', value: props.phoneNumber },
      { name: 'phone_number_verified', value: 'true' },
      { name: 'custom:role', value: props.role }
    ];
    if (props.shopId) {
      userAttributes.push({ name: 'custom:shopId', value: props.shopId });
    }
    this.userPoolUser = new CfnUserPoolUser(this, 'User', {
      userPoolId: props.userPoolId,
      username: userEmail,
      userAttributes: userAttributes,
      messageAction: 'SUPPRESS',
    });
  }
}


export interface AppCognitoPoolProps {
  readonly prefix: string;
  readonly removalPolicy: RemovalPolicy;
  readonly runtime: Runtime;
  readonly lambdaLayer: PythonLayerVersion;
}

export class AppCognitoPool extends Construct {
  public readonly prefix: string;
  public readonly userPool: UserPool;
  public readonly identityPool: CfnIdentityPool;
  public readonly authenticatedDefaultRole: IRole;
  public readonly unauthenticatedRole: IRole;
  public readonly authenticatedShopOwnerRole: IRole;
  public readonly authenticatedAdminRole: IRole;
  public readonly runtime: Runtime;
  public readonly removalPolicy: RemovalPolicy;

  constructor(scope: Construct, id: string, props: AppCognitoPoolProps) {
    super(scope, id);

    this.prefix = props.prefix;
    this.runtime = props.runtime;
    this.removalPolicy = this.removalPolicy || RemovalPolicy.DESTROY;

    const region = Stack.of(this).region;
    const account = Stack.of(this).account;

    //
    // Cognito User Pool
    //
    // Create a Cognito User Pool with 2 custom attributes called 'role' and 'id'
    // AdvancedSecurityMode: 'ENFORCED' is not set since it requires a "Cognito Plus" feature plan and this is just a
    // demo
    // amazonq-ignore-next-line
    this.userPool = new UserPool(this, 'UserPool', {
      userPoolName: `${this.prefix}-UserPool`,
      removalPolicy: this.removalPolicy,
      selfSignUpEnabled: true,
      signInAliases: { email: true },
      autoVerify: { email: true },
      passwordPolicy: {
        minLength: 8,
        requireLowercase: true,
        requireDigits: true,
        requireSymbols: false,
        requireUppercase: true,
      },
      customAttributes: {
        role: new StringAttribute({ mutable: true }),
        shopId: new StringAttribute({ mutable: true }),
      },
    });
    // Add an App Client to the User Pool
    const userPoolClient = this.userPool.addClient('UserPoolClient', {
      userPoolClientName: `${this.prefix}-UserPoolClient`,
      generateSecret: false,
      authFlows: {
        userPassword: true,
      },
      preventUserExistenceErrors: true,
    });


    //
    // Cognito Identity Pool
    //
    // Create a Cognito Identity Pool with both authenticated and guest access
    // amazonq-ignore-next-line
    this.identityPool = new CfnIdentityPool(this, 'IdentityPool', {
      identityPoolName: `${this.prefix}-IdentityPool`,
      allowUnauthenticatedIdentities: true,
      cognitoIdentityProviders: [{
        clientId: userPoolClient.userPoolClientId,
        providerName: this.userPool.userPoolProviderName,
      }],
    });
    // Set the attributes for Access Control
    new CfnIdentityPoolPrincipalTag(this, 'IdentityPoolPrincipalTag', {
      identityPoolId: this.identityPool.ref,
      identityProviderName: this.userPool.userPoolProviderName,
      useDefaults: false,
      principalTags: {
        cognito_user_sub: 'sub',
        cognito_app_id: 'aud',
        shopId: 'custom:shopId',
        role: 'custom:role',
      },
    });
    // Create IAM Roles for the authenticated users
    const autenticatedRoleTrustPoliy = new FederatedPrincipal(
      'cognito-identity.amazonaws.com',
      {
        StringEquals: { 'cognito-identity.amazonaws.com:aud': this.identityPool.ref },
        'ForAnyValue:StringLike': { 'cognito-identity.amazonaws.com:amr': 'authenticated' },
      },
      'sts:AssumeRoleWithWebIdentity'
    ).withSessionTags();
    this.authenticatedDefaultRole = new Role(this, 'AuthenticatedRole', {
      roleName: `${this.prefix}-IdentityPool-AuthenticatedDefaultRole`,
      assumedBy: autenticatedRoleTrustPoliy,
    });
    this.authenticatedShopOwnerRole = new Role(this, 'ShopOwnerRole', {
      roleName: `${this.prefix}-IdentityPool-ShopOwnerRole`,
      assumedBy: autenticatedRoleTrustPoliy,
    });
    this.authenticatedAdminRole = new Role(this, 'AdminRole', {
      roleName: `${this.prefix}-IdentityPool-AdminRole`,
      assumedBy: autenticatedRoleTrustPoliy,
    });
    // Create a single IAM Role for the guest users
    this.unauthenticatedRole = new Role(this, 'UnauthenticatedRole', {
      roleName: `${this.prefix}-IdentityPool-UnauthenticatedRole`,
      assumedBy: new FederatedPrincipal(
        'cognito-identity.amazonaws.com',
        {
          StringEquals: { 'cognito-identity.amazonaws.com:aud': this.identityPool.ref },
          'ForAnyValue:StringLike': { 'cognito-identity.amazonaws.com:amr': 'unauthenticated' },
        },
        'sts:AssumeRoleWithWebIdentity'
      ),
    });
    // Attach the roles to the Identity Pool
    new CfnIdentityPoolRoleAttachment(this, 'IdentityPoolRoleAttachment', {
      identityPoolId: this.identityPool.ref,
      roles: {
        authenticated: this.authenticatedDefaultRole.roleArn,
        unauthenticated: this.unauthenticatedRole.roleArn,
      },
      roleMappings: {
        cognito: {
          type: 'Rules',
          ambiguousRoleResolution: 'AuthenticatedRole',
          identityProvider: `${this.userPool.userPoolProviderName}:${userPoolClient.userPoolClientId}`,
          rulesConfiguration: {
            rules: [
              {
                claim: 'custom:role',
                value: 'shop_owner',
                roleArn: this.authenticatedShopOwnerRole.roleArn,
                matchType: 'Equals',
              },
              {
                claim: 'custom:role',
                value: 'admin',
                roleArn: this.authenticatedAdminRole.roleArn,
                matchType: 'Equals',
              }
            ],
          },
        },
      }
    });

    //
    // Create Test Cognito Users in the User Pool
    //
    // Create a list containing the users information
    const testUsersData = [];
    for (let i = 1; i <= 2; i++) {
      testUsersData.push({
        username: `Shop${i}Owner`,
        phoneNumber: `+4179${i.toString().repeat(7)}`,
        role: 'shop_owner',
        shopId: i.toString().padStart(4, '0'),
      });
    }
    testUsersData.push({
      username: 'AdminUser',
      phoneNumber: '+41790000000',
      role: 'admin',
    });
    testUsersData.push({
      username: `RegisteredCustomer1`,
      phoneNumber: '+41790000001',
      role: 'customer',
    });
    // Create the Cognito Users
    const testUsers = testUsersData.map((user) =>
      new CognitoUserPoolUser(this, user.username, {
        userPoolId: this.userPool.userPoolId,
        username: user.username,
        phoneNumber: user.phoneNumber,
        role: user.role,
        shopId: user.shopId,
      })
    );
    // create a list of all the user's username'
    const userNames = testUsers.map((user) => user.userPoolUser.username);

    //
    // Create a Secrets Manager Secrets to store the User Pool user password for all test users
    //
    // In this demo we use the same password for all users
    const userPassword = new Secret(this, 'Secret', {
      secretName: `${this.prefix}-TestUSersPassword`,
      generateSecretString: {
        secretStringTemplate: JSON.stringify({}),
        generateStringKey: 'password',
        passwordLength: 8,
        excludePunctuation: true,
        includeSpace: false,
      },
      description: 'Password for all test users in the Cognito User Pool',
      removalPolicy: this.removalPolicy
    });

    //
    // Custom Resource to set the password for all test users
    //
    // Note: We can't use the AWSCustomResource construct to simply call the AdminSetUserPassword
    // since Custom Resources do not handle Secrets safely
    // See https://github.com/aws/aws-cdk/issues/9815
    // and https://github.com/aws-cloudformation/cloudformation-coverage-roadmap/issues/341
    //
    // Create the IAM Role and Policy for the Single Lambda FUnction
    const policyDocument = new PolicyDocument({
      statements: [
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'cognito-idp:AdminSetUserPassword',
          ],
          resources: [this.userPool.userPoolArn],
        }),
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'logs:CreateLogGroup',
            'logs:CreateLogStream',
            'logs:PutLogEvents',
          ],
          resources: [`arn:aws:logs:${region}:${account}:log-group:/aws/lambda/*`],
        }),
      ]
    })
    const singletonRole = new Role(this, 'SingletonRole', {
      roleName: `${this.prefix}-cr-set-test-user-password-role`,
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
    });
    new Policy(this, 'SingletonPolicy', {
      policyName: 'lambda-cr-set-test-user-password-policy',
      document: policyDocument,
      roles: [singletonRole],
    });
    userPassword.grantRead(singletonRole);
    // Create the Custom Resource to set the passwords
    const setTestUsersPasswordLambda = new SingletonFunction(this, 'Singleton', {
      uuid: 'd53dc712-66f7-45af-9b54-fd9fc793a2db',
      functionName: `${this.prefix}-cr-set-test-user-password`,
      code: Code.fromAsset('resources/lambdas/set_test_users_password'),
      handler: 'main.lambda_handler',
      role: singletonRole,
      timeout: Duration.minutes(1),
      runtime: this.runtime,
      environment: {
        USER_POOL_ID: this.userPool.userPoolId,
        USER_PASSWORD_SECRET_ARN: userPassword.secretArn,
        USERS: userNames.join(','),
      },
      logRetention: RetentionDays.ONE_WEEK,
      layers: [props.lambdaLayer],
    });
    new CustomResource(this, 'CustomResource', {
      serviceToken: setTestUsersPasswordLambda.functionArn,
    });
  }
}
