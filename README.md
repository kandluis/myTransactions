# MyTransactions Tracker

A barebones Node.js app using [Express 4](http://expressjs.com/) to track transcations.

## Running Locally

Make sure you have [Node.js](http://nodejs.org/) and the [Heroku CLI](https://cli.heroku.com/) installed. 

The below has been tested with Node v10.7.0 and NPM v6.2.0. You can check your current version by running:
```sh
$ node --version
$ npm --version
```

You can also update them by running, found at [SO](https://stackoverflow.com/questions/11284634/upgrade-node-js-to-the-latest-version-on-mac-os):
```sh
sudo npm cache clean -f
sudo npm install -g n
sudo n stable
```

```sh
$ git clone <TODO> # or clone your own fork
$ cd <TODO>
$ npm install
$ heroku local web
```

Your app should now be running on [localhost:5000](http://localhost:5000/).

## Creating on Heroko
If you want to deploy your own version to heroku, run the following. Note that you'll need to be logged-in

```
$ heroku create
$ git push heroku master
$ heroku open
```

If you'd rather just deploy to the current lenslet.herokuapp.com version:
```
$ heroku git:remote -a lenslet
```

The above command will just add a heroku remote pointing to the existing lenslet.herokuapp.com site.

## Deploying on Heroko
Once the heroku app is created (or associated with the existing lenslet.herokuapp.com site), deployment is as simple as pushing:
```
$ git push heroku master
```