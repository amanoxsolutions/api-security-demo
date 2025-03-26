import { Construct } from "constructs";
import { Stage, StageProps, RemovalPolicy } from 'aws-cdk-lib';
import { Runtime } from 'aws-cdk-lib/aws-lambda';
import { ApiSecurityAppStack } from "./app/app-stack";

export interface ApiSecurityPipelineStageProps extends StageProps {
  readonly prefix: string;
  readonly uniqueSuffix: string;
  readonly runtime: Runtime;
  readonly removalPolicy: RemovalPolicy;
}

export class ApiSecurityPipelineStage extends Stage {

  constructor(scope: Construct, id: string, props: ApiSecurityPipelineStageProps) {
    super(scope, id, props);

    const properties = {
      prefix: props.prefix,
      s3Suffix: props.uniqueSuffix,
      runtime: props.runtime,
      removalPolicy: props.removalPolicy,
    };

    // Stack to deploy the Application
    new ApiSecurityAppStack(this, "AppStack", properties);

  }
}
