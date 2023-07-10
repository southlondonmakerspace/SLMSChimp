#!/bin/bash

KEY=""
N=5

curl -sS "https://us3.api.mailchimp.com/3.0/reporting/surveys/07fd9d9ce0bc/responses" --user "anystring:$KEY" > responses.json
EXIT=0;
jq -r .responses[].response_id responses.json | (
    while read SURVEY; do
        if [ $EXIT -eq 1 ]; then exit; fi
        SURVEY_PATH="./surveys/$SURVEY.json" 
        if [ ! -f "$SURVEY_PATH" ]; then
            (
                    echo "Fetching $SURVEY";
                    RESPONSE_CODE=$(curl -s -o "$SURVEY_PATH" -w "%{http_code}" "https://us3.api.mailchimp.com/3.0/reporting/surveys/07fd9d9ce0bc/responses/$SURVEY" --user "anystring:$KEY")
                    if [ $RESPONSE_CODE != "200" ]; then
                        echo "Bad HTTP code. 429 is rate limit and you got $RESPONSE_CODE";
                        rm "$SURVEY_PATH";
                        EXIT=1;
                        exit;
                    fi;
                    sleep 3s;
            ) &
                if [[ $(jobs -r -p | wc -l) -ge $N ]]; then wait -n; fi
        fi;
    done;
    wait
)