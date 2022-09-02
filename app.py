#!/usr/bin/env python3

from aws_cdk import core

from stack import app_stack


app = core.App()
app_stack.LambdaAppStack(app, "mint_scraper")

app.synth()
