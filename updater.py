import argparse
import logging
from typing import cast
import pygsheets

import auth
import config
import remote

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main(argv=None) -> None:
    """Main function for the updater script."""
    parser = argparse.ArgumentParser(
        description="Update Google Sheet categories based on rules in config.yaml."
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Do not write changes to Google Sheets.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Dump updated transactions to local CSV.",
    )

    args = parser.parse_args(argv)

    logger.info("Loading configurations...")
    creds = auth.GetCredentials()

    logger.info("Connecting to Google Sheets...")
    client = pygsheets.authorize(custom_credentials=creds.sheets)
    sheet = client.open(config.GLOBAL.WORKSHEET_TITLE)

    logger.info(
        "Fetching transactions from worksheet "
        f"'{config.GLOBAL.RAW_TRANSACTIONS_TITLE}'..."
    )
    all_txns_ws = sheet.worksheet_by_title(title=config.GLOBAL.RAW_TRANSACTIONS_TITLE)
    original_df = all_txns_ws.get_as_df(numerize=False)
    original_df = original_df[config.GLOBAL.COLUMN_NAMES]

    logger.info("Applying category rules and normalizations...")
    transformed = remote.ApplyCategoryRules(original_df)

    # Calculate difference before filtering ignored transactions
    changed_mask = original_df["Category"] != transformed["Category"]
    num_changed = changed_mask.sum()

    if num_changed > 0:
        logger.info(f"Found {num_changed} transactions with category changes.")
        diff_df = original_df[changed_mask]
        logger.info("Sample category changes (max 20):")
        for idx, row in diff_df.head(20).iterrows():
            idx_int = cast(int, idx)
            new_cat = transformed.loc[idx_int]["Category"]
            logger.info(
                f"  Row {idx_int + 2}: {row['Date']} | {row['Merchant']} | "
                f"'{row['Category']}' -> '{new_cat}'"
            )
    else:
        logger.info("No category changes detected.")

    logger.info(
        "Running standard transaction clean-up "
        "(filtering ignored, accounts mapping normalizations)..."
    )
    cleaned = remote._cleanTxns(transformed)

    num_filtered = len(transformed) - len(cleaned)
    if num_filtered > 0:
        logger.info(f"Filtered out {num_filtered} ignored/skipped transactions.")

    if args.dry_run:
        logger.info("[DRY RUN] Bypassing Google Sheets update.")
        # Default to dumping CSV in dry run for verification
        output_file = "transactions_updated.csv"
        cleaned.to_csv(output_file, index=False)
        logger.info(f"[DRY RUN] Saved updated local copy to {output_file}")
    else:
        logger.info("Uploading updated transactions to Google Sheets...")
        remote.UpdateGoogleSheet(sheet=sheet, transactions=cleaned, accounts=None)
        logger.info("Google Sheet update complete!")
        if args.debug:
            output_file = "transactions_updated.csv"
            cleaned.to_csv(output_file, index=False)
            logger.info(f"Saved updated local copy to {output_file}")


if __name__ == "__main__":
    main()
