# slmschimp
### version 1.0

to run
 - .env file with credentials
 - create venv and activate,
 - pip3 install -r requirements.txt and

if in doubt: https://docs.python.org/3/library/venv.html

To run successfully, the script needs an event for an open evening on the
Discourse calendar. The automation is suspended on open evenings (every
other Wednesday). 

### Usage
~~~
usage: slmschimp.py [-h] [-s] [-a] [-f] [-q] [-ci] [-ll LOG_LEVEL]

slmschimp.py: SLMS slightly over-engineered Mailchimp Automation

options:
  -h, --help            show this help message and exit
  -s, --status          show current status of list members
  -a, --auto            automate all processes
  -f, --force           force automate campaign despite today being open eve.
  -q, --quiet           no log messages to Discourse.
  -ci, --campaign-info  show URL and date from both campaign and Discourse event.
  -ll LOG_LEVEL, --log-level LOG_LEVEL
                        set log level from: ERROR, DEBUG, WARNING, CRITICAL. Default: INFO
~~~

### .env file

Please make sure to have that in .gitignore

~~~
#.env for slmschimp.py | save as ".env"

# Mailchimp
DC="datacenter"
API_KEY="mailchimp_api_key_goes_here"
LIST_ID="mailchimp_list_id"
SURVEY_ID="mailchimp_survey_id"

# Discourse
USER_API_KEY="discourse_user_api_key"
USER_API_CLIENT_ID="client_id"
WELCOME_TABLE_TOPIC_ID=00000
LOG_TOPIC_ID=00000
~~~

# timer.py

Simple utility that invokes slmschimp.py every 12 hours by default.

~~~
usage: timer.py [-h] [-hrs HOURS]

Run a script and sleep for a specified number of hours.

options:
  -h, --help            show this help message and exit
  -hrs HOURS, --hours HOURS
                        Number of hours to sleep between script runs
~~~
