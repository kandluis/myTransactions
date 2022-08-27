#!/usr/bin/env python3

from aws_cdk import core

from lambda_app import lambda_app_stack


app = core.App()
lambda_app_stack.LambdaAppStack(app, "mint_scraper")

app.synth()
