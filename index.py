# Lambda handler code.
import scraper


def lambda_handler(event, context):
  """Handler for when this script is run on AWS Lambda."""

  scraper.scrape_and_upload(
      options=scraper.ScraperOptions(
          types='all', showBrowser=False, cookies=None, session_path=None)
  )
