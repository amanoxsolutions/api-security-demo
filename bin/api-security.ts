#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { ApiSecurityStack } from '../lib/api-security-stack';

const app = new cdk.App();
new ApiSecurityStack(app, 'ApiSecurityStack', {
  /* If you don't specify 'env', this stack will be environment-agnostic.
   * Account/Region-dependent features and context lookups will not work,
   * but a single synthesized template can be deployed anywhere. */

  /* Uncomment the next line to specialize this stack for the AWS Account
   * and Region that are implied by the current CLI configuration. */
  // env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },

  /* Uncomment the next line if you know exactly what Account and Region you
   * want to deploy the stack to. */
  // env: { account: '123456789012', region: 'us-east-1' },

  /* For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html */
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION
  },
  prefix: 'api-security-demo',
  repoName: 'amanoxsolutions/aws-challenge-api-security',
  codestarConnectionArn: 'arn:aws:codeconnections:eu-west-1:645143808269:connection/a5f194f5-62b7-4345-9a89-2cb50dc04f09',
});
