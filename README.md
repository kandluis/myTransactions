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


Additionally, you need a `keys.json` file containing valid keys to be used when accessing the Google Spreadsheet. This is just a JSON file that you should be able to download from the Google Cloud Console. You need to attach in the `GOOGLE_SHEETS_CREDENTIALS` section above as a single string.

Note that we rely on `pipenv` to automatically load the variables from `.env` into your environment. If you are not using `pipenv`, you will need to load them in some other way.


## Python Requirements

### `pipenv` and `pyenv`

As of the latest update, we recommend leveraging `pipenv` and `pyenv` to maintain a hermetic static for dependencies. The other options are left here only for reference as they are not maintained/tested often.

On Mac, make sure you have [Homebrew](https://brew.sh/) installed. You can install `pipenv` and `pyenv` with:

```sh
brew install pipenv
brew install pyenv
````

After installing, you navigate to the root of the project directory, and run:

```sh
pipenv install
```

This will install all the required dependencies as well as the appropriate Python version (using pyenv). You can then run:

```sh
pipenv run python scraper.py --type='all'
```

To run the script with these installs, or you can jump into the installed Python environment at the shell bevel with:

```sh
pipenv shell
````


### [Deprecated] conda
I recommend using `conda`, since it's quite easy to handle specific python versions.  You can use `miniconda` from the instructions [here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/macos.html).

After install, you can create a new `conda` environment (with Python 3.10) which is the latest tested version, and activate it.

```sh
conda create -n txn python=3.10
```

On the first activation, install the required packages.

```sh
pip install -r requirements.txt
```

### [Deprecated] virtualenv & virtualenvwrapper
You can use of `virtualenv` and `virtualenvwrapper` to set this up appropriately. The provided `run.sh` script assumes these exist, but obviously you can install everything at the top-level Python environment if you so choose. This is probably a bad idea, though.

Note: This package has only been tested on Python 3.7. In fact, it appears that installation of pandas in 3.8 fails due to compilation errors.

If you already have `virtualenvwrapper` installed, then simply create a new environment and run:

```
pip install -r requirements.txt
```

This will install the required libraries.

## Chrome Driver
The Chrome driver used is, by default, located in the current working directory of the script. However, for running in Heroku, install the `heroku-buildpack-chromedriver` and `heroku-buildpack-google-chrome` and set the following:

```
CHROMEDRIVER_PATH=/app/.chromedriver/bin
GOOGLE_CHROME_BIN=/app/.apt/usr/bin/google_chrome
```

# Running the script.

Update `run.sh` to match the right locations and setup (note that it currently works by relying on virtualenv). Note that the script *by default* must be run from the top-level directory, if you want to use the included chrome driver. 

You might want to consider running the `scraper.py` file with `--debug` if something goes wrong.

# Type Checking

You should be able to type check by running:

```
mypy scraper.py
```

# Deploy To Heroku

To deploy to our heroku server, just run:
```
git push heroku master
```

# Version

1.0.0
