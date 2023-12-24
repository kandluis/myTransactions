# Set-Up

## Environment Variables

To setup the scraper, you need to follow the following steps.

First, a `.env` file at the top-level directory needs to exists. It should look like:

```sh
USERNAME=<TODO>
PASSWORD=<TODO>
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


## Chrome Driver
The Chrome driver used is, by default, located in the current working directory of the script. However, for running in Heroku, install the `heroku-buildpack-chromedriver` and `heroku-buildpack-google-chrome` and set the following:

```sh
CHROMEDRIVER_PATH=/app/.chromedriver/bin
GOOGLE_CHROME_BIN=/app/.apt/usr/bin/google_chrome
```

# Type Checking

For development purposes, you want to also install the dev dependencies by running `pipenv install -d`.

You should be able to type check by running:

```sh
pipenv run mypy .
```

# Unit Tests

You can run all unit tests with the command:
```sh
pipenv run pytest
```

# Formatting

You can run all formatting with the command:
```sh
pipenv run black .
```

# Deploy to fly.io

## Setup

The first thing you want to do is install `flyctl`. You can do this on Mac trivially if you have `brew` installed using:

```sh
brew install flyctl
```

## Deployment
We migrated our Heroku stack. We now leverage a custom-built Docker container that gets deployed to `fly.io` for our purposes. 

The deployment of the container should happen automatically using Github actions whenever you push the repo. Just leverage that.

### Wait, I need to deploy manualyl!

We recommend you build it remotely. This happens by default when simply running. You can install `flyctl` with `brew install flyctl`:

```sh
flyctl deploy --remote-only
```

### Testing Locally
You can build this container locally and run it:
```sh
docker build -t mint_scraper .
```

Once built, you can test locally by running the image. Note that it might fail due to binary incompatibitlies between the driver versions.
```sh
docker run --env-file=.env -e USE_CHROMEDRIVER_ON_PATH=1 mint_scraper:latest python scraper.py --type='all'
```

## Debugging

If you're running into issues, you want to debug by ssh'ing into the machine. 

1. Download and install [Wireguard](https://www.wireguard.com/install/).
2. Run `flyctl wireguard create` and use the output config for a new tunnel in Wireguard. Activate this tunnel.
3. Run `flyctl ssh issue --agent` to populate a 24hr certificate in your local agent.
4. RUn `flyctl ssh console --app mint-scraper-fly`

For the last command, you can replace `mint-scraper-fly` with the name of the app. This will connect to a running instance of `mint-scraper-fly` using a basic shell. You can now debug to your heart's content.


# Version

2.0.0
