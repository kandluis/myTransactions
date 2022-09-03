import os

from aws_cdk import (
    aws_ecr_assets as ecr,
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

    lambdaFn = lambdas.DockerImageFunction(
        self, "Singleton",
        code=lambdas.DockerImageCode.from_image_asset(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
            platform=ecr.Platform.LINUX_AMD64,
        ),
        timeout=core.Duration.seconds(600),
        memory_size=512,
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
