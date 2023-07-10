 #!/bin/bash
 
 jq 'select(.results[] | select(.question_id == "29486" and .answer == "No")) | .contact.email' surveys/*