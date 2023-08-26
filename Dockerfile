FROM heroku/heroku:22
RUN useradd -m heroku
RUN mkdir /app
WORKDIR /app
ENV HOME /app
ENV PORT 8080

# This is a hack that lets us download all the chromedrivers, chrome, etc.
# That were installed locally on heroku at time of deployment (9/4/22).
# This means it's hard/impossible to update this.
# In general, we'll try to keep fixed to this version.
RUN curl "https://nautilikassets.s3.us-west-1.amazonaws.com/archive.tgz" | tar xzf - --strip 1 -C /app
# Delete old chromedriver, we'll fetch our own by default.
RUN rm -f /app/.chromedriver/bin/chromedriver

# Copy our local files over to /app so we can update the local installation.
COPY . /app

# Update the dependencies as specified by new Pipfile.
RUN /bin/bash /app/entrypoint.sh pipenv install --system --deploy

# Default entrypoint.
ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"]

# Own the app, drop to heroku user.
RUN chown -R heroku:heroku /app && \
    chmod a+x /app/serve.sh
USER heroku



