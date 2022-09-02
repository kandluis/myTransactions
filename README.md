# Set-Up

## AWS

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


### [DEPRECATED] conda
I recommend using `conda`, since it's quite easy to handle specific python versions.  You can use `miniconda` from the instructions [here](https://docs.conda.io/projects/conda/en/latest/user-guide/install/macos.html).

After install, you can create a new `conda` environment (with Python 3.10) which is the latest tested version, and activate it.

```sh
conda create -n txn python=3.10
```

On the first activation, install the required packages.

```sh
pip install -r requirements.txt
```

### [DEPRECATED] virtualenv & virtualenvwrapper
You can use of `virtualenv` and `virtualenvwrapper` to set this up appropriately. The provided `run.sh` script assumes these exist, but obviously you can install everything at the top-level Python environment if you so choose. This is probably a bad idea, though.

Note: This package has only been tested on Python 3.7. In fact, it appears that installation of pandas in 3.8 fails due to compilation errors.

If you already have `virtualenvwrapper` installed, then simply create a new environment and run:

```
pip install -r requirements.txt
```

This will install the required libraries.

## [DEPRECATED] Chrome Driver
The Chrome driver used is, by default, located in the current working directory of the script. However, for running in Heroku, install the `heroku-buildpack-chromedriver` and `heroku-buildpack-google-chrome` and set the following:

```
CHROMEDRIVER_PATH=/app/.chromedriver/bin
GOOGLE_CHROME_BIN=/app/.apt/usr/bin/google_chrome
```

# Running the script.

You can run it using `pipenv` locally by executing:

```sh
pipenv run scraper.py --type='all'
```


You might want to consider running the `scraper.py` file with `--debug` if something goes wrong.

# Type Checking

You should be able to type check by running:

```
mypy scraper.py
```

# Deploy to AWS Lambda

The script is written so it can be deployed to AWS Lambda to run periodically. You can also follow the instructions here to test locally before deployment to confirm everything is working as expected.

See this [scraper examples](https://github.com/aws-samples/lambda-web-scraper-example) for more details. The below assumes that you have the [AWS CDK](https://aws.amazon.com/cdk/) and [Docker](https://www.docker.com/) installed. Note you will need to have Node.JS intalled (see `aws` [prereqs](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)).

You want to make sure you've set-up the appropriave development dependencies (see `Pipfile`).

## Build Docker Image

Run the following command from the project directory (Docker must be installed and running) to build the required Docker and AWS outputs.

```sh
docker build -t mint_scraper .
docker run -i -v `pwd`/dist:/opt/ext -t mint_scraper
```

For the next step, you'll need your AWS ID and default region. Since you installed the `aws` CLI previously, you can find this information with the following commands:

```sh
aws sts get-caller-identity
aws configure get region
```

Finally, you'll want to bootstrap the application. This requires that you have all the developer dependencies installed.

```sh
pipenv install -d
# As per above.
pipenv run cdk bootstrap aws://<AWS ID>/<REGION> 
# Perform deployment of application.
pipenv cdk deploy
``` 

# [DEPRECATED] Deploy To Heroku

To deploy to our heroku server, just run:
```
git push heroku master
```

# Version

1.0.0
