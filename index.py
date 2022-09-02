# Lambda handler code.
from scraper import main


def lambda_handler(event, context):
    """Handler for when this script is run on AWS Lambda."""
    main()
