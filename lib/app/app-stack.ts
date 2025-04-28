import { Stack, StackProps, RemovalPolicy, CustomResource, Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { Runtime, Code, Tracing, SingletonFunction } from 'aws-cdk-lib/aws-lambda';
import { PythonFunction, PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';
import { RetentionDays } from 'aws-cdk-lib/aws-logs';
import { OpenApiGatewayToLambda } from '@aws-solutions-constructs/aws-openapigateway-lambda';
import { Asset } from 'aws-cdk-lib/aws-s3-assets';
import { Table, AttributeType, BillingMode, ProjectionType } from "aws-cdk-lib/aws-dynamodb";
import { Effect, Policy, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from "aws-cdk-lib/aws-iam";
import { AppCognitoPool } from './cognito';


export interface ApiSecurityAppStackProps extends StackProps {
  readonly prefix: string;
  readonly s3Suffix: string;
  readonly removalPolicy: RemovalPolicy;
  readonly runtime: Runtime;
}

export class ApiSecurityAppStack extends Stack {
  public readonly prefix: string;
  public readonly s3Suffix: string;
  public readonly removalPolicy: RemovalPolicy;
  public readonly runtime: Runtime;

  constructor(scope: Construct, id: string, props: ApiSecurityAppStackProps) {
    super(scope, id, props);

    this.prefix = props.prefix;
    this.s3Suffix = props.s3Suffix;
    this.runtime = props.runtime;
    this.removalPolicy = props.removalPolicy || RemovalPolicy.DESTROY;

    const region = Stack.of(this).region;
    const account = Stack.of(this).account;

    //
    // DynamoDB Table
    //
    const table = new Table(this, "OrdersTable", {
      tableName: `${this.prefix}-OrdersTable`,
      partitionKey: {
        name: "PK",
        type: AttributeType.STRING
      },
      sortKey: {
        name: "SK",
        type: AttributeType.STRING
      },
      billingMode: BillingMode.PAY_PER_REQUEST,
      removalPolicy: this.removalPolicy,
    })
    table.addGlobalSecondaryIndex({
      indexName: "GSI1",
      partitionKey: {
        name: "GSI1-PK",
        type: AttributeType.STRING
      },
      sortKey: {
        name: "GSI1-SK",
        type: AttributeType.STRING
      },
      projectionType: ProjectionType.ALL
    })
    table.addGlobalSecondaryIndex({
      indexName: "GSI2",
      partitionKey: {
        name: "GSI2-PK",
        type: AttributeType.STRING
      },
      sortKey: {
        name: "GSI2-SK",
        type: AttributeType.STRING
      },
      projectionType: ProjectionType.ALL
    });

    //
    // Create a Lambda layer with helper functions attached to all Lambda functions
    //
    const helpersLayer = new PythonLayerVersion(this, 'helperLayer', {
      entry: './resources/lambdas/helpers_layer',
      description: `${props.prefix}-helpers Lambda Layer`,
      compatibleRuntimes: [props.runtime],
      layerVersionName: `${props.prefix}-helpers-layer`,
      removalPolicy: RemovalPolicy.RETAIN, // we need to keep the old layer version otherwise the custom resource will fail
    });

    //
    // Cognito
    //
    const cognito = new AppCognitoPool(this, 'Cognito', {
      prefix: this.prefix,
      removalPolicy: this.removalPolicy,
      runtime: this.runtime,
      lambdaLayer: helpersLayer,
    });

    //
    // API Gateway & Lambda Functions
    //
    const apiDefinitionAsset = new Asset(this, 'ApiDefinitionAsset', {
      path: './resources/openapi/api-definition.yaml'
    });

    const default_lambda_props = {
      runtime: this.runtime,
      handler: 'main.lambda_handler',
      logRetention: RetentionDays.ONE_WEEK,
      tracing: Tracing.ACTIVE,
      layers: [helpersLayer],
      environment: {
        CORS_ORIGIN: 'temp-value',
        TABLE_NAME: table.tableName,
        COGNITO_USER_POOL_ID: cognito.userPool.userPoolId,
      },
      timeout: Duration.seconds(10)
    };

    const apiGatwayToLambda = new OpenApiGatewayToLambda(this, 'OpenApiGatewayToLambda', {
      apiDefinitionAsset,
      apiIntegrations: [
        {
          id: 'list-products',
          lambdaFunctionProps: {
            ...default_lambda_props,
            functionName: `${this.prefix}-list-products`,
            code: Code.fromAsset('./resources/lambdas/list_products'),
          }
        },
        {
          id: 'place-order',
          lambdaFunctionProps: {
            ...default_lambda_props,
            functionName: `${this.prefix}-place-order`,
            code: Code.fromAsset('./resources/lambdas/place_order')
          }
        },
        {
          id: 'get-order',
          lambdaFunctionProps: {
            ...default_lambda_props,
            functionName: `${this.prefix}-get-order`,
            code: Code.fromAsset('./resources/lambdas/get_order'),
          }
        },
        {
          id: 'get-shop',
          lambdaFunctionProps: {
            ...default_lambda_props,
            functionName: `${this.prefix}-get-shop`,
            code: Code.fromAsset('./resources/lambdas/get_shop'),
          }
        },
        {
          id: 'regenerate-token',
          lambdaFunctionProps: {
            ...default_lambda_props,
            functionName: `${this.prefix}-regenerate-shop-token`,
            code: Code.fromAsset('./resources/lambdas/regenerate_shop_token'),
          }
        },
        {
          id: 'list-orders',
          lambdaFunctionProps: {
            ...default_lambda_props,
            functionName: `${this.prefix}-list-shop-orders`,
            code: Code.fromAsset('./resources/lambdas/list_shop_orders'),
          }
        },
        {
          id: 'get-sales',
          lambdaFunctionProps: {
            ...default_lambda_props,
            functionName: `${this.prefix}-get-shop-sales`,
            code: Code.fromAsset('./resources/lambdas/get_shop_sales'),
          }
        },
        {
          id: 'get-service-stats',
          lambdaFunctionProps: {
            ...default_lambda_props,
            functionName: `${this.prefix}-get-service-stats`,
            code: Code.fromAsset('./resources/lambdas/get_service_stats'),
          }
        },
      ]
    });


    //
    // Add IAM Policy to All Lambda Functions
    //
    // List the IAM Roles of all Lambda functions
    const lambdaRoles = apiGatwayToLambda.apiLambdaFunctions
      .filter(lambda => lambda.lambdaFunction !== undefined)
      .map(lambda => lambda.lambdaFunction!.role!);
    // Add permissions to the Lambda functions
    for (var role of lambdaRoles) {
      // Add DynamoDB permissions
      table.grantReadWriteData(role);
      // Grant permissions to access the Cognito User Pool
      cognito.userPool.grant(role, 'cognito-idp:AdminGetUser');
    }

    //
    // Grant permissions to the IAM Roles of the authenticated and unauthenticated users of the Cognito Identity Pool
    // to access API Gateway
    //
    // Create and attach a policy to the authenticated role granting access to the API Gateway
    const minimumPolicy = new PolicyStatement({
      actions: ['execute-api:Invoke'],
      resources: [
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/POST/order`,
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/GET/order/*`,
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/GET/products`
      ],
    });
    cognito.authenticatedDefaultRole.addToPrincipalPolicy(minimumPolicy);
    // Create and attach a policy to the guest role granting access to the API Gateway
    cognito.unauthenticatedRole.addToPrincipalPolicy(minimumPolicy);
    // Add policiy to the user mapping roles based on their role
    cognito.authenticatedShopOwnerRole.addToPrincipalPolicy(new PolicyStatement({
      actions: ['execute-api:Invoke'],
      resources: [
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/POST/order`,
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/GET/order/*`,
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/GET/shop/\${aws:PrincipalTag/shopId}`,
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/GET/shop/\${aws:PrincipalTag/shopId}/*`,
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/POST/shop/\${aws:PrincipalTag/shopId}/*`,
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/GET/products`
      ],
    }));
    cognito.authenticatedAdminRole.addToPrincipalPolicy(new PolicyStatement({
      actions: ['execute-api:Invoke'],
      resources: [
        `arn:aws:execute-api:${region}:${account}:${apiGatwayToLambda.apiGateway.restApiId}/prod/GET/service-stats`
      ],
    }));

    //
    // Custom Resource to Prefill Table with Test Data
    //
    const policyDocument = new PolicyDocument({
      statements: [
        new PolicyStatement({
          effect: Effect.ALLOW,
          actions: [
            'dynamodb:DescribeTable',
            'dynamodb:BatchWriteItem',
            'dynamodb:GetItem',
            'dynamodb:PutItem',
            'dynamodb:UpdateItem',
          ],
          resources: [`arn:aws:dynamodb:${region}:${account}:table/${table.tableName}`],
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
    // Create the role for the custom resource Lambda
    // We do this manually to be able to give it a human readable name
    const singletonRole = new Role(this, 'SingletonRole', {
      roleName: `${this.prefix}-cr-prefill-table-with-testdata-role`,
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
    });
    // Create the inline policy separately to avoid circular dependencies
    new Policy(this, 'SingletonPolicy', {
      policyName: 'lambda-cr-prefill-table-with-testdata-policy',
      document: policyDocument,
      roles: [singletonRole],
    });
    cognito.userPool.grant(singletonRole, 'cognito-idp:ListUsers');
    const customResourceLambda = new SingletonFunction(this, 'Singleton', {
      functionName: `${this.prefix}-cr-prefill-table-with-testdata`,
      uuid: '7a9e8df1-faa7-4b63-9e74-62a99d443267',
      code: Code.fromAsset('resources/lambdas/prefill_table_with_testdata'),
      handler: 'main.lambda_handler',
      role: singletonRole,
      timeout: Duration.minutes(1),
      runtime: this.runtime,
      environment: {
        TABLE_NAME: table.tableName,
        COGNITO_USERPOOL_ID: cognito.userPool.userPoolId,
      },
      logRetention: RetentionDays.ONE_WEEK,
      layers: [helpersLayer],
    });
    new CustomResource(this, 'CustomResource', {
      serviceToken: customResourceLambda.functionArn,
    });

    // python lambda function to call migrations/ensure_shop_token/index.py
    const ensureShopTokenLambda = new PythonFunction(this, 'EnsureShopTokenLambda', {
        entry: 'resources/lambdas/migrations/ensure_shop_token',
        runtime: this.runtime,
        handler: 'lambda_handler',
        logRetention: RetentionDays.THREE_MONTHS,
        environment: {
          TABLE_NAME: table.tableName,
        },
        layers: [helpersLayer],
        timeout: Duration.minutes(5)
    });
    table.grantReadWriteData(ensureShopTokenLambda);
  }
}
