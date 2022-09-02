from aws_cdk import (
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambdas,
    aws_sam as sam,
    core
)


class LambdaAppStack(core.Stack):

  def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
    super().__init__(scope, id, **kwargs)

    with open("index.py", encoding="utf8") as fp:
      handler_code = fp.read()

    role = iam.Role(
        self, 'mintScraperRole',
        assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'))

    role.add_to_policy(iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        resources=["*"],
        actions=['events:*']))

    role.add_to_policy(iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        resources=["arn:aws:iam::*:role/AWS_Events_Invoke_Targets"],
        actions=['iam:PassRole']))

    role.add_to_policy(iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        resources=["*"],
        actions=[
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
        ]))

    role.add_to_policy(iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        resources=["*"],
        actions=["s3:*"]))

    role.add_to_policy(iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        resources=["*"],
        actions=["lambda:*"]))

    role.add_to_policy(iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        resources=["*"],
        actions=["sns:*"]))

    lambdaFn = lambdas.Function(
        self, "Singleton",
        code=lambdas.InlineCode(handler_code),
        handler="index.lambda_handler",
        timeout=core.Duration.seconds(600),
        runtime=lambdas.Runtime.PYTHON_3_9,
        memory_size=512,
        environment=dict(PATH="/opt"),
        role=role
    )

    rule = events.Rule(
        self, "Rule",
        schedule=events.Schedule.cron(
            minute='59',
            hour='11',
            month='*',
            week_day='*',
            year='*'),
    )
    rule.add_target(targets.LambdaFunction(lambdaFn))

    ac = lambdas.AssetCode("./dist")

    layer = lambdas.LayerVersion(self, "mint-scraper", code=ac,
                                 description="mint-scraper layer",
                                 compatible_runtimes=[
                                     lambdas.Runtime.PYTHON_3_9],
                                 layer_version_name='mint-scraper-layer')
    lambdaFn.add_layers(layer)

    wrangler_layer = sam.CfnApplication(
        self,
        "wrangler-layer",
        location=sam.CfnApplication.ApplicationLocationProperty(
            application_id="arn:aws:serverlessrepo:us-east-1:336392948345"
                           ":applications/aws-data-wrangler-layer-py3-9",
            # From https://github.com/awslabs/aws-data-wrangler/releases
            semantic_version="2.16.1",
        ),
    )
    wrangler_layer_arn = wrangler_layer.get_att(
        "Outputs.WranglerLayer38Arn").to_string()
    wrangler_layer_version = lambdas.LayerVersion.from_layer_version_arn(
        self, "wrangler-layer-version", wrangler_layer_arn)
    lambdaFn.add_layers(wrangler_layer_version)
