# Set-Up

## Environment Variables

To setup the scraper, you need to follow the following steps.

First, a `.env` file at the top-level directory needs to exists. It should look like:

```
MINT_EMAIL=<TODO>
MINT_PASSWORD=<TODO>
EMAIL_PASSWORD=<TODO>
CHROME_DRIVER_PATH=<TODO>  // Defaults to os.getcwd() if not provided.
MFA_TOKEN=<TODO>
GOOGLE_SHEETS_CREDENTIALS=<TODO> // The keys.json file for the Google sheets service, as a string.
```
Note that MFA_TOKEN is needed for Mint accounts with 2-FA enabled, and corresponds to the token that Google Authenticator uses. With this token, the app can generate OTP on its own. If not provided, we will fall-back to text-based method and this will require user interaction.


Additionally, you need a `keys.json` file containing valid keys to be used when accessing the Google Spreadsheet. This is just a JSON file that you should be able to download from the Google Cloud Console.

## Python Requirements

I recommend you make use of `virtualenv` and `virtualenvwrapper` to set this up appropriately. The provided `run.sh` script assumes these exist, but obviously you can install everything at the top-level Python environment if you so choose. This is probably a bad idea, though.

Note: This package has only been tested on Python 3.7. In fact, it appears that installation of pandas in 3.8 fails due to compilation errors.

If you already have `virtualenvwrapper` installed, then simply create a new environment and run:

```
pip install -r requirements.txt
```

This will install the required libraries.

## Chrome Driver
The Chrome driver used is, by default, located in the current working directory of the script. However, for running in Heroku, install the heroku-buildpack-chromedriver and update the `GOOGLE_CHROME_BIN` environment variable to `GOOGLE_CHROME_BIN`.

To update, run:
```
heroku buildpacks:publish heroku/chromedriver master
```

# Running the script.

Update `run.sh` to match the right locations and setup (note that it currently works by relying on virtualenv). Note that the script *by default* must be run from the top-level directory, if you want to use the included chrome driver. 

You might want to consider running the `scraper.py` file with `--debug` if something goes wrong.

# Type Checking

You should be able to type check by running:

```
mypy scraper.py
```