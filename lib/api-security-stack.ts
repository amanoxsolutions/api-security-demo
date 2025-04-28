import { Stack, StackProps, RemovalPolicy } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { CodePipeline, CodePipelineSource, ShellStep } from 'aws-cdk-lib/pipelines';
import { ComputeType, LinuxBuildImage, BuildSpec } from 'aws-cdk-lib/aws-codebuild';
import { Bucket, BucketAccessControl, BucketEncryption } from 'aws-cdk-lib/aws-s3'
import { Runtime } from 'aws-cdk-lib/aws-lambda';
import { ApiSecurityPipelineStage } from './pipeline-stage';
import murmurhash = require('murmurhash');


function getShortHashFromString(strToConvert: string, hashLength: number = 6): string {
  // Use murmur hash to generate a hash from the string and extract the first characters as a string
  return murmurhash.v3(strToConvert).toString(16).substring(0, hashLength);
}

export interface ApiSecurityStackProps extends StackProps {
  readonly prefix: string;
  readonly codestarConnectionArn: string;
  readonly runtime?: Runtime;
  readonly removalPolicy?: RemovalPolicy;
  readonly repoName: string;
  readonly branchName?: string;
}

export class ApiSecurityStack extends Stack {
  constructor(scope: Construct, id: string, props: ApiSecurityStackProps) {
    super(scope, id, props);

    const removalPolicy = props.removalPolicy || RemovalPolicy.DESTROY;
    const runtime = props.runtime || Runtime.PYTHON_3_12;
    const branchName = props.branchName || 'main';

    // Create a unique suffix based on the AWS account number, repo name and the branchName
    // to be used for resources this is used for S3 bucket bucket names for example
    const uniqueSuffix = getShortHashFromString(`${this.account}-${props.repoName}-${branchName}`, 8);

    // Create the code artifact S3 bucket in order to be able to set the object deletion and
    // removalPolicy
    // amazonq-ignore-next-line
    const artifactBucket = new Bucket(this, 'ArtifactBucket', {
      bucketName: `${props.prefix}-pipeline-artifacts-bucket-${uniqueSuffix}`,
      accessControl: BucketAccessControl.PRIVATE,
      encryption: BucketEncryption.S3_MANAGED,
      removalPolicy: removalPolicy,
      autoDeleteObjects: removalPolicy === RemovalPolicy.DESTROY,
      enforceSSL: true
    });


    const buildSpec = BuildSpec.fromObject({
      version: '0.2',
      phases: {
        install: {
          'runtime-versions': {
            python: '3.12'
          },
          commands: [
            'pip install poetry'
          ]
        },
      },
      cache: {
        paths: [
          'node_modules/**/*',
          '.poetry/**/*'
        ]
      }
    });


    const pipeline = new CodePipeline(this, 'Pipeline', {
      pipelineName: `${props.prefix}-pipeline`,
      artifactBucket: artifactBucket,
      synth: new ShellStep('Synth', {
        input: CodePipelineSource.connection(props.repoName, branchName,
          {
            connectionArn: props.codestarConnectionArn,
            codeBuildCloneOutput: true,
          }
        ),
        // We pass to the CodeBuild job the branchName as a context parameter
        commands: [`git checkout ${branchName}`, 'cat .git/HEAD', 'npm ci', 'npm run build', 'npx cdk synth --no-previous-parameters']
      }),
      dockerEnabledForSynth: true,
      assetPublishingCodeBuildDefaults: {
        buildEnvironment: {
          buildImage: LinuxBuildImage.STANDARD_7_0,
          computeType: ComputeType.SMALL,
        },
        partialBuildSpec: buildSpec
      },
    });

    // We use addWave instead of addStage because addStage in the aws-cdk-lib/pipelines CodePipeline construct
    // does not mean 'add a stage to the pipeline' but 'deploy an application stack'
    // See GitHub discussion: https://github.com/aws/aws-cdk/discussions/23888
    // We could achieve the same result by adding a 'pre' action in the application deployment stage but we
    // wanted to have the unit testing in a complete different stage
    pipeline.addWave('UnitTests', {
      pre: [
        new ShellStep('RunPytestUnitTests', {
          commands: [
            'echo running Pytest Unit Tests',
            'pip install poetry',
            // Verify installations
            'python3 --version',
            'poetry --version',
            'cd resources',
            'poetry install --with dev',
            'poetry run pytest'
          ],
          env: {
            NODE_ENV: 'test',
          }
        })
      ]
    });

    pipeline.addStage(new ApiSecurityPipelineStage(this, 'Stage', {
      stageName: `${props.prefix}-app-stack`,
      prefix: props.prefix,
      uniqueSuffix: uniqueSuffix,
      runtime: runtime,
      removalPolicy: removalPolicy,
    }));
  }
}
