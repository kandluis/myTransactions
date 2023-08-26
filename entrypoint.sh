# Reset environment to heroku-like.
for f in /app/.profile.d/*.sh; do . $f; done
PATH=/app/.chromedriver/bin:$PATH
eval "exec $@"
