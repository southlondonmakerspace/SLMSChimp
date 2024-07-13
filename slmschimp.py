#!/usr/bin/env python3
#
# South London Makerspace way over-engineered MailChimp Survey Invitation
# Automation version 1.0
# slmschimp.py (perhaps slmswoemsia.py would be more appropriate?)
# Thank you, Kyle, for the inspiration and the support.
# Geraetefreund, 2023-09-09 (Nine Oh Nine!)


import os
import json
import re
import time
import requests
import logging
import argparse
from tabulate import tabulate
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()  # loads variables from .env file into environment.

""" setup for argparse """
parser = argparse.ArgumentParser(
    description='slmschimp.py: SLMS slightly over-engineered Mailchimp '
                'Automation')
parser.add_argument('-s', '--status', action='store_true',
                    help='show current status of list members')
parser.add_argument('-a', '--auto', action='store_true',
                    help='automate all processes')
parser.add_argument('-f', '--force', action='store_true',
                    help='force automation despite today being open eve.')
parser.add_argument('-q', '--quiet', action='store_true',
                    help="no log messages to Discourse.")
parser.add_argument('-ci', '--campaign-info', action='store_true',
                    help='show URL and date from both campaign '
                         'and Discourse event.')
parser.add_argument('-ll', '--log-level', help='set log level from:'
                                               ' ERROR, DEBUG, WARNING, CRITICAL. Default: INFO')
args = parser.parse_args()

""" setup for logging """

""" Set the logging level (DEBUG, WARNING, ERROR, CRITICAL. default=INFO) """
try:
    log_level = getattr(logging, args.log_level)
except TypeError:
    log_level = 'INFO'


# Custom handler to collect logs, because we send them to Discourse \o/
class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_records = []

    def emit(self, record):
        # Append that log record to the list
        self.log_records.append(self.format(record))


logger = logging.getLogger()
logger.setLevel(log_level)

# Create a formatter
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s",
                              datefmt='%Y-%m-%d %H:%M:%S')

# Create a handler for stdout
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Create a custom ListHandler to collect log records
list_handler = ListHandler()
list_handler.setFormatter(formatter)
logger.addHandler(list_handler)


class DataProvider:
    """ survey_responses takes a long time to download. DataProvider makes
     sure we only download them once. """

    def __init__(self):
        self.api = MailChimpAPI()
        self.survey_responses = None
        self.list_members_info = None
        self.last_campaign_content = None

    def get_survey_responses(self):
        if self.survey_responses is None:
            self.survey_responses = self.api.get_survey_responses()
        return self.survey_responses

    def get_list_members_info(self):
        if self.list_members_info is None:
            self.list_members_info = self.api.get_list_members_info()
        return self.list_members_info

    def get_total_items(self):
        result = self.list_members_info['total_items']
        return result if result else None

    def get_last_campaign_content(self):
        if self.last_campaign_content is None:
            self.last_campaign_content = (
                self.api.get_campaign_content(self.api.last_campaign_id()))
        return self.last_campaign_content


class MailChimpAPI:
    """ MailChimp API related methods """

    def __init__(self):
        self.dc = os.getenv('DC')
        self.api_key = os.getenv('API_KEY')
        self.survey_id = os.getenv('SURVEY_ID')
        self.list_id = os.getenv('LIST_ID')
        self.url = f"https://{self.dc}.api.mailchimp.com/3.0"
        self.auth = ("anystring", self.api_key)
        self.iso_date = datetime.now().date().isoformat()
        self.discourse = Discourse()

    def ping(self):
        url = self.url + "/ping"
        response = None
        try:
            response = requests.get(url, auth=self.auth)
        except Exception as error:
            logging.error(f"ping: {error}")
            return response.json()
        return response

    def get_list_members_info(self):
        """ Get info about survey responses on our list."""
        url = self.url + f"/lists/{self.list_id}/members"
        payload = {'exclude_fields': 'members.interests,members.stats'}
        response = None
        try:
            response = requests.get(url, params=payload, auth=self.auth)
        except Exception as error:
            logging.error(f"get_list_members_info: {error}")
            return response
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"get_list_members_info: {response.status_code}")
            return response

    def get_survey_responses(self):
        url = self.url + f"/reporting/surveys/{self.survey_id}/responses"
        logging.debug("get_survey_responses: ...takes a little while...")
        response = None
        try:
            response = requests.get(url, auth=self.auth)
        except Exception as error:
            logging.error(f"get_survey_responses: {error}")
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"get_survey_responses: "
                          f"response status code {response.status_code}")
            return response

    def get_survey_result(self, response_id):
        url = (self.url +
               f"/reporting/surveys/{self.survey_id}/responses/{response_id}")
        response = None
        try:
            response = requests.get(url, auth=self.auth)
        except Exception as error:
            logging.error(f"get_survey_result: {error}")
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"get_survey_result:"
                          f" response status code {response.status_code}")
            return response

    def campaign_info(self, status):
        """ gets last sent, draft, sending etc...
        campaign info, make sure to receive only our list_id. """
        url = self.url + "/campaigns"
        payload = {'count': 1,
                   'status': f'{status}',
                   'since_create_time': '2023-08-08T08:08:00+00:00',
                   'sort_field': 'create_time',
                   'sort_dir': 'DESC',
                   'list_id': f'{self.list_id}'}
        response = None
        try:
            response = requests.get(url, params=payload, auth=self.auth)
        except Exception as error:
            logging.error(f"campaign_info: {error}")
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(f"campaign_info: response status code "
                          f"{response.status_code}")
            return response

    def last_campaign_id(self):
        """ returns campaign_id from last successfully sent campaign """
        try:
            data = self.campaign_info("sent")
            logging.debug(f"last_campaign id: Last successfully sent "
                          f"campaign_id: {data['campaigns'][0].get('id')}")
            return data["campaigns"][0].get('id')
        except Exception as error:
            logging.error(f"last_campaign_id: Can not get last_campaign_id. "
                          f"{error}")

    def last_campaign_web_id(self):
        """ returns campaign_id from last successfully sent campaign """
        try:
            data = self.campaign_info("sent")
            logging.debug(f"last_campaign web_id: Last successfully sent "
                          f"campaign_id: {data['campaigns'][0].get('id')}")
            return data["campaigns"][0].get('web_id')
        except Exception as error:
            logging.error(f"last_campaign_id: Can not get last_campaign_id. "
                          f"{error}")

    def last_campaign_send_time(self):
        """ returns campaign_id from last successfully sent campaign """
        try:
            data = self.campaign_info("sent")
            logging.debug(f"last_campaign send_time: Last successfully sent"
                          f" campaign_id: {data['campaigns'][0].get('id')}")
            return data["campaigns"][0].get('send_time')
        except Exception as error:
            logging.error(f"last_campaign_id: Can not get"
                          f" last_campaign_id. {error}")

    def draft_campaign_id(self):
        try:
            data = self.campaign_info("save")
            return data['campaigns'][0].get('id')
        except IndexError:
            logging.debug("draft_campaign_id: No Campaign draft present.")
            return None

    def delete_campaign(self, campaign_id):
        url = self.url + f"/campaigns/{campaign_id}"
        response = None
        try:
            response = requests.delete(url, auth=self.auth)
        except Exception as error:
            logging.error(f"delete_campaign: {error}")
        if response.status_code == 204:
            logging.debug(f"delete_campaign: "
                          f"Successfully deleted campaign: {campaign_id}")
            return response
        else:
            logging.error(f"delete_campaign: campaign_id '{campaign_id}' "
                          f"does not exist, response status code "
                          f"{response.status_code}")

    def create_campaign(self):
        url = self.url + "/campaigns"
        # tag = self.tag_search(f'Invited-{self.iso_date}')

        response = None
        data = {"type": "regular",
                "recipients": {
                    "list_id": "59cc0c8cb4",
                    "list_is_active": True,
                    "list_name": "Member Capacity Mailing List",
                    "segment_text": "<p class=\"!margin--lv0 display--inline\">Contacts that match "
                                    "<strong>all</strong> of the following conditions:</p><ol id=\"conditions\" "
                                    "class=\"small-meta text-transform--none\"><li class=\"margin--lv1 "
                                    "!margin-left-right--lv0\">Matches a custom advanced segment</li></ol><span>For a "
                                    "total of <strong>0</strong> emails sent.</span>",
                    "segment_opts": {
                        "saved_segment_id": 10201693,
                        "match": "all"
                    }
                },
                "settings": {
                    "subject_line": "Membership Invite to the Makerspace",
                    "preview_text": "Please join us as a member!",
                    "title": "Membership invite",
                    "from_name": "South London Makerspace",
                    "reply_to": "info@southlondonmakerspace.org",
                    "use_conversation": False,
                    "to_name": "*|FNAME|*",
                    "folder_id": "",
                    "authenticate": True,
                    "auto_footer": False,
                    "inline_css": False,
                    "auto_tweet": False,
                    "fb_comments": True,
                    "template_id": 10091262,
                    "drag_and_drop": False},
                "tracking": {
                    "opens": True,
                    "html_clicks": True,
                    "text_clicks": True,
                    "goal_tracking": False,
                    "ecomm360": False,
                    "google_analytics": "",
                    "clicktale": ""
                },
                "social_card": {
                    "image_url": "",
                    "description": "",
                    "title": ""
                },
                "content_type": "multichannel"
                }
        data["settings"]["title"] = "Membership invite " + self.iso_date
        try:
            response = requests.post(url, json=data, auth=self.auth)
        except Exception as error:
            logging.error(f"create_campaign: {error}")
        if response.status_code == 200:
            return response
        else:
            logging.error(f"create_campaign: "
                          f"failed to add campaign, response status code "
                          f"{response.status_code}")
            return response

    def get_campaign_content(self, campaign_id):
        url = self.url + f"/campaigns/{campaign_id}/content"
        payload = {'fields': 'html'}
        response = None
        try:
            response = requests.get(url, params=payload, auth=self.auth)
        except Exception as error:
            logging.error(f"get_campaign_content: Failed to retrieve campaign "
                          f"content for campaign_id: {campaign_id}. {error}")
        if response.status_code == 200:
            logging.debug(f"get_campaign_content: Successfully retrieved "
                          f"campaign content for campaign_id: {campaign_id}")
            return response.json()
        else:
            logging.error(f"get_campaign_content: Failed to retrieve campaign "
                          f"content for campaign_id: {campaign_id}. "
                          f"{response.status_code}")
            return response

    def set_campaign_content(self, campaign_id, content):
        """ upload content to campaign_draft """
        url = self.url + f"/campaigns/{campaign_id}/content"
        response = None
        try:
            response = requests.put(url, json=content, auth=self.auth)
        except Exception as error:
            logging.error(f"set_campaign_content: Failed to upload content to "
                          f"campaign_id: {campaign_id}. {error}")
        if response.status_code == 200:
            logging.debug(f"set_campaign_content: Successfully updated "
                          f"campaign content for campaign_id: {campaign_id}")
            return response
        else:
            logging.error(f"set_campaign_content: Failed to upload content to"
                          f" campaign_id: {campaign_id}. "
                          f"{response.status_code}")
            return response.status_code

    def send_campaign(self, campaign_id):
        url = self.url + f"/campaigns/{campaign_id}/actions/send"
        response = None
        if self.draft_campaign_id():
            try:
                response = requests.post(url, auth=self.auth)
            except Exception as error:
                logging.error(f"send_campaign: Failed sending campaign with "
                              f"id '{campaign_id}'. {error}")
            if response.status_code == 204:
                logging.debug(f"send_campaign: Successfully sent campaign "
                              f"with id '{campaign_id}'. "
                              f"Response: {response.status_code}")
                return response
            if response.status_code == 400:
                logging.error(f"send_campaign: Failed sending campaign - halting script.")
                raise SystemExit("send_campaign: Script stopped due to response status code 400.")
            else:
                logging.error(f"send_campaign: Failed sending campaign. "
                              f"Response: {response.status_code} ")
            return response
        else:
            logging.debug(f"send_campaign: Campaign not sent: Missing "
                          f"campaign_id.")

    def check_sending(self):
        data = self.campaign_info("sending")['total_items']
        return True if data else False

    def add_tag(self, contact_id, tag):
        url = self.url + f"/lists/{self.list_id}/members/{contact_id}/tags"
        payload = {'tags': [{'name': f'{tag}', 'status': 'active'}]}
        response = None
        try:
            response = requests.post(url, json=payload, auth=self.auth)
        except Exception as error:
            logging.error(f"add_tag: {error}")
        if response.status_code == 204:
            logging.debug(f"add_tag: Successfully added tag '{tag}' to "
                          f"contact_id '{contact_id}'.")
        else:
            logging.error(f"add_tag: Failed to add tag '{tag}' to contact_id"
                          f" '{contact_id}'. Response: {response.status_code}")

    def rem_tag(self, contact_id, tag):
        url = self.url + f"/lists/{self.list_id}/members/{contact_id}/tags"
        payload = {'tags': [{'name': f'{tag}', 'status': 'inactive'}]}
        response = None
        try:
            response = requests.post(url, json=payload, auth=self.auth)
        except Exception as error:
            logging.error(f"add_tag: {error}")
        if response.status_code == 204:
            logging.debug(f"rem_tag: Successfully removed tag '{tag}' to "
                          f"contact_id '{contact_id}'.")
        else:
            logging.error(f"rem_tag: Failed to remove tag '{tag}' to contact_id"
                          f" '{contact_id}'. Response: {response.status_code}")

    def list_tags(self, contact_id):
        url = self.url + f"/lists/{self.list_id}/members/{contact_id}/tags"
        """ Thank you mailchimp for defaulting to 10. NOT! """
        params = {'count': 100}
        response = None
        try:
            response = requests.get(url, params=params, auth=self.auth)
        except Exception as error:
            logging.error(f"list_tags: {error}")

        if response.status_code == 200:
            logging.debug(f"list_tags: Successfully retrieved tags for "
                          f"contact_id '{contact_id}'.")
        else:
            logging.error(f"list_tags: Failed retrieving tags for contact_id "
                          f"'{contact_id}'. Response: {response.json()}")
        return response.json()

    def tag_search(self, tag):
        url = self.url + f"/lists/{self.list_id}/tag-search"
        params = {'name': f'{tag}'}
        response = None
        try:
            response = requests.get(url, params=params, auth=self.auth)
        except Exception as error:
            logging.error(f"tag_search: {error}")

        if response.status_code == 200:
            logging.debug(f"tag_search: Searched mailchimp for {tag}. ")
        else:
            logging.error(f"tag_search: Failed retrieving tag: {tag}  ")
        return response.json()

    def archive(self, contact_id):
        url = self.url + f"/lists/{self.list_id}/members/{contact_id}"
        response = None
        try:
            response = requests.delete(url, auth=self.auth)
        except Exception as error:
            logging.error(f"archive: {error}")

        if response.status_code == 204:
            logging.debug(f"archive: Successfully archived contact_id "
                          f"'{contact_id}'.")
        else:
            logging.error(f"archive: Failed archiving contact_id "
                          f"'{contact_id}'. {response.json()}")

    def unarchive(self, contact_id):
        """ MC has no endpoint to unarchive, set status to unsubscribed. """
        url = self.url + f"/lists/{self.list_id}/members/{contact_id}"
        payload = {'status': 'unsubscribed'}
        response = None
        try:
            response = requests.patch(url, json=payload, auth=self.auth)
        except Exception as error:
            logging.error(f"unarchive: {error}")

        if response.status_code == 200:
            logging.debug(f"unarchive: Successfully unarchived contact_id "
                          f"'{contact_id}'.")
        else:
            logging.error(f"unarchive: Unable to unarchive contact_id "
                          f"'{contact_id}'. {response.json()}")
        return response

    def subscribe(self, contact_id, email_address):
        url = self.url + f"/lists/{self.list_id}/members/{contact_id}"
        payload = {'skip_merge_validation': True}
        data = {'status': 'subscribed'}
        response = None
        try:
            response = requests.patch(url, params=payload,
                                      json=data, auth=self.auth)
        except Exception as error:
            logging.error(f"subscribe: {error}")

        if response.status_code == 200:
            logging.debug(f"subscribe: Successfully subscribed  "
                          f"'{email_address}'.")
        else:
            logging.error(f"subscribe: Failed subscribing '{email_address}'."
                          f" {response.json()}")

    def unsubscribe(self, contact_id, email_address):
        url = self.url + f"/lists/{self.list_id}/members/{contact_id}"
        payload = {'skip_merge_validation': True}
        data = {'status': 'unsubscribed'}
        response = None
        try:
            response = requests.patch(url, params=payload, json=data,
                                      auth=self.auth)
        except Exception as error:
            logging.error(f"unsubscribe: {error}")

        if response.status_code == 200:
            logging.debug(f"unsubscribe: Successfully unsubscribed "
                          f"'{email_address}'.")
        else:
            logging.error(f"unsubscribe: Failed subscribing '{email_address}'."
                          f" {response.json()}")


# noinspection SpellCheckingInspection
class Automation:
    def __init__(self, list_members, surveys):
        self.api = MailChimpAPI()
        self.list_members_info = list_members
        self.survey_responses = surveys

    def total_items(self):
        total_items = self.list_members_info['total_items']
        if total_items == 0:
            return None
        else:
            return total_items

    def contact_id(self, index):
        try:
            contact_id = self.list_members_info['members'][index].get('contact_id')
            return contact_id
        except IndexError:
            logging.info(f"contact_id: Nothing to do. No survey response for"
                         f" index {index}.")
            return None

    def get_field(self, contact_id, field_name):
        contact_details = ['email', 'contact_id', 'status', 'full_name']
        survey_responses_fields = ['response_id', 'submitted_at']
        survey_result_fields = ['is_18+', 'discourse_name']
        field_value = None
        if field_name in contact_details:
            for response in self.survey_responses['responses']:
                if contact_id == response.get('contact').get('contact_id'):
                    field_value = response.get('contact').get(field_name).strip()
        elif field_name in survey_responses_fields:
            for response in self.survey_responses['responses']:
                if contact_id == response.get('contact').get('contact_id'):
                    field_value = response.get(field_name)
        elif field_name in survey_result_fields:
            for response in self.survey_responses['responses']:
                if contact_id == response.get('contact').get('contact_id'):
                    response_id = response.get('response_id')
                    survey = automation.api.get_survey_result(response_id)
                    if field_name == 'is_18+':
                        """ Fall back check if survey has been filled in before age check was implemented."""
                        """ Checking whether the tag was added by mailchimp"""
                        tags = self.api.list_tags(contact_id)['tags']
                        field_value = any(tag['id'] == 10181290 for tag in tags)
                    elif field_name == 'discourse_name':
                        query = next(item['answer'] for item in survey['results'] if item['question_id'] == "29030")
                        return query.strip().replace(" ", "").split("\n")[-1] if query else None
        elif field_name == 'has_invite_tag':
            tags = self.api.list_tags(contact_id)['tags']
            # field_value = any(item['id'] == 10183946 for item in tags)
            # field_value = any(item['id'] == 10201597 for item in tags)
            field_value = any(item['id'] == 10201605 for item in tags)  # tag = slmschimp
        return field_value

    def restore_mark(self):
        """ just for dev/debug purposes, so we can play with the script"""
        contact_id1 = "4eeba0d90e3e0431271a87937d62ea13"
        contact_id2 = "74cee5f369732ed3a9f496033536afd3"
        self.api.unarchive(contact_id1)
        self.api.unarchive(contact_id2)

    def remove_mark(self):
        contact_id1 = "4eeba0d90e3e0431271a87937d62ea13"
        contact_id2 = "74cee5f369732ed3a9f496033536afd3"
        self.api.rem_tag(contact_id1, 'slmschimp')

        self.api.rem_tag(contact_id2, 'slmschimp')
        self.api.archive(contact_id1)
        self.api.archive(contact_id2)

    @staticmethod
    def find_campaign_date_and_url(campaign_content):
        pattern = r"is(?: on)? ([A-Za-z]+)(?:,)? (\d{1,2})(?:st|nd|rd|th)?\s*([A-Za-z]+)"
        match = re.search(pattern, json.dumps(campaign_content))
        result = []
        if match:
            day_name, day_number, month_name = match.groups()[0:3]
            month_dict = {"January": 1, "February": 2, "March": 3, "April": 4,
                          "May": 5, "June": 6, "July": 7, "August": 8,
                          "September": 9, "October": 10, "November": 11,
                          "December": 12}
            month_number = month_dict[month_name]
            today = datetime.today()
            target_date = today.replace(day=int(day_number), month=month_number)
            date = target_date.date()
            result.append(date)

            url_pattern = r"https:\/\/discourse\.southlondonmakerspace\.org\/t\/[^/]+\/\d+"
            url_match = re.findall(url_pattern, json.dumps(campaign_content))
            result.append(url_match[0])
            return result
        else:
            logging.error("get_openeve_date_and_url: Could not find date or URL.")

    def update_campaign_content(self, campaign_content, discourse_date_and_url):
        """ compares Disocurse URL and Date for next OE-Event and updates if necessary """
        campaign_date_and_url = self.find_campaign_date_and_url(campaign_content)
        if campaign_date_and_url == list(discourse_date_and_url):
            logging.info(f'update_campaign_content: Campaign Date and URL up '
                         f'to date. Nothing to do.')
            return campaign_content
        else:
            logging.info(f'update_campaign_content: Campaign Date and URL ' f'need updating.')
            old_date_match = re.search(r'\w+, \d{2}(st|nd|rd|th)? \w+', campaign_content['html'])
            if old_date_match:
                old_date = old_date_match.group()
            else:
                old_date = None
            campaign_date = old_date
            discourse_date = discourse_date_and_url[0].strftime('%A, %d %B')
            old_url = campaign_date_and_url[1]
            new_url = discourse_date_and_url[1]
            updated_content = re.sub(campaign_date, discourse_date, campaign_content['html'])
            updated_content = updated_content.replace(old_url, new_url)
            campaign_content['html'] = updated_content
        return campaign_content

    def status(self):
        if self.total_items():
            logging.info(f"status: There are currently "
                         f"{self.total_items()} survey results.")
            member_data_list = []
            for member in list(range(self.total_items())):
                contact_id = self.contact_id(member)
                email = self.get_field(contact_id, 'email')
                member_status = self.get_field(contact_id, 'status')
                response_id = self.get_field(contact_id, 'response_id')
                is_18 = self.get_field(contact_id, 'is_18+')
                invited = self.get_field(contact_id, 'has_invite_tag')
                member_data = {
                    'Member': member,
                    'Email': email,
                    'Status': member_status,
                    'Is 18+': is_18,
                    'Response ID': response_id,
                    'Invited': invited}
                member_data_list.append(member_data)
            tabular_data = [[member_data['Member'],
                             member_data['Email'],
                             member_data['Status'],
                             member_data['Is 18+'],
                             member_data['Response ID'],
                             member_data['Invited']] for member_data in member_data_list]
            # column headers, oh so pretty.
            headers = ['Member', 'Email', 'Status', 'Is 18+', 'Response ID', 'Invited']
            print(tabulate(tabular_data, headers=headers, tablefmt="simple"))
        else:
            logging.info(f"status: We have no survey results. Nothing to do.")

    def automate(self):
        iso_date = datetime.now().date().isoformat()
        num_surveys = self.total_items()
        processed_ids = []
        if num_surveys is None:
            logging.info("automate: No Survey results. Nothing to"
                         " do. Everything's Chimpy!")
        else:
            logging.info(f"automate: Started automation for "
                         f"{num_surveys} list members.")
            for survey in list(range(num_surveys)):
                contact_id = self.contact_id(survey)
                if self.get_field(contact_id, 'status') == "Subscribed":
                    logging.debug(f"automate: List member {survey} already subscribed.")
                else:
                    """ needs to be done this way, unfortunately. Bruteforce4tw! """
                    self.api.unsubscribe(contact_id, self.get_field(contact_id, 'email'))
                    time.sleep(2)
                    self.api.subscribe(contact_id, self.get_field(contact_id, 'email'))
                if not self.get_field(contact_id, 'has_invite_tag'):
                    if self.get_field(contact_id, 'is_18+'):
                        self.api.add_tag(contact_id, f"Invited-{iso_date}")
                        self.api.add_tag(contact_id, 'slmschimp')
                    elif not self.get_field(contact_id, 'is_18+'):
                        logging.warning(f"automate: Member {survey} not 18+. Adding tag 'NoSend' and unsubscribing.")
                        self.api.add_tag(contact_id, 'NoSend')
                        self.api.unsubscribe(contact_id, self.get_field(contact_id, 'email'))
                elif self.get_field(contact_id, 'has_invite_tag'):
                    logging.debug(f"automate: Member {survey} already tagged: 'slmschimp'.")
                    self.api.add_tag(contact_id, f'Invited-{iso_date}')
                    self.api.add_tag(contact_id, 'slmschimp')  # this is here for a reason! (restore_mark())
            if self.api.draft_campaign_id() is None:
                self.api.create_campaign()
                campaign_content = self.api.get_campaign_content(self.api.last_campaign_id())
                updated_content = self.update_campaign_content(campaign_content, Discourse.get_openeve_date_and_url())
                self.api.set_campaign_content(self.api.draft_campaign_id(), updated_content)
            else:
                logging.info(f'automate: Draft campaign {self.api.draft_campaign_id} present!')
                self.api.create_campaign()
                campaign_content = self.api.get_campaign_content(self.api.last_campaign_id())
                updated_content = self.update_campaign_content(campaign_content, Discourse.get_openeve_date_and_url())
                self.api.set_campaign_content(self.api.draft_campaign_id(), updated_content)
            try:
                self.api.send_campaign(self.api.draft_campaign_id())
            except Exception as error:
                logging.error(f"automate: Sending campaign failed: {error}")
                raise Exception("automate: Failed sending campaign.")
            while self.api.check_sending():
                logging.debug("automate: Campaign still sending. Waiting 5s...")
                time.sleep(5)
            for survey in list(reversed(range(num_surveys))):
                """ I use reversed here for no reason! Scratching_head..."""
                contact_id = self.contact_id(survey)
                if self.get_field(contact_id, 'has_invite_tag'):
                    processed_ids.append(contact_id)
                    self.api.archive(contact_id)
                elif not self.get_field(contact_id, 'is_18+'):
                    logging.warning(f"automate: List member is not 18+: "
                                    f"{self.get_field(contact_id, 'email')}")
            logging.info(f"automate: Successfully processed "
                         f"{num_surveys} list members.")
            logging.info(f"automate: Successfully sent campaign: "
                         f"[{self.api.last_campaign_id()}]"
                         f"(https://us3.admin.mailchimp.com/reports/summary?"
                         f"id={self.api.last_campaign_web_id()})")
        return processed_ids

    def collect_member_info(self, collected_ids):
        user_info = []
        for contact_id in collected_ids:
            result = [
                datetime.now().date().isoformat(),  # item[0]
                self.get_field(contact_id, 'full_name'),  # item[1]
                self.get_field(contact_id, 'email'),  # item[2]
                self.get_field(contact_id, 'response_id'),  # item[3]
                self.api.last_campaign_id(),  # item[4]
                self.get_field(contact_id, 'discourse_name'),  # item[5]
                contact_id]  # item[6]
            user_info.append(result)
        return user_info


class Discourse:
    """ Discourse related methods"""
    headers = {'User-Api-Key': os.getenv('USER_API_KEY'),
               'User-Api-Client-Id': os.getenv('USER_API_CLIENT_ID')}
    base_url = 'https://discourse.southlondonmakerspace.org'

    @staticmethod
    def get_openeve_date_and_url():
        logging.debug("get_openeve_date_and_url: Getting URL and Date from"
                      " Discourse calendar event.")
        # url = Discourse.base_url + '/c/events.json'
        url = Discourse.base_url + '/c/events/l/calendar.json'
        response = None
        open_eves = []  # all events that are open evenings
        try:
            response = requests.get(url)
        except Exception as error:
            logging.error(f"get_openeve_date_and_url: {error} requests: "
                          f"{response.status_code} ")
        if response.status_code == 200:
            topics = response.json()['topic_list']['topics']
            for topic in topics:
                title_lower = topic['title'].lower()
                if "open" in title_lower and "evening" in title_lower:
                    event_date = datetime.strptime(topic['event'].get('start').split("T")[0], "%Y-%m-%d").date()
                    event_url = (Discourse.base_url + '/t/'
                                 + topic['slug'] + "/" + str(topic['id']))
                    open_eves.append((event_date, event_url))
            closest_future_event = min(((date, link) for date, link in open_eves if date >= datetime.now().date()),
                                       default=None)
            #  This also returns a date event if today is Open Evening! 
            if closest_future_event is None:
                logging.warning("get_openeve_date_and_url: No future OE event found on discourse.")
            return closest_future_event  # returns None if we don't have an event! useful for not inviting!!!
        else:
            logging.critical(f"get_openeve_date_and_url: Could not retrieve openeve info. :(")
            return response

    @staticmethod
    def send_to_topic(raw_message):
        if isinstance(raw_message, list):
            raw_message = '\n'.join(raw_message)
        url = Discourse.base_url + '/posts.json'
        raw_content = raw_message
        data = {'topic_id': os.getenv('LOG_TOPIC_ID'),
                'raw': raw_content}
        response = requests.post(url, headers=Discourse.headers, data=data)
        if response.status_code == 200:
            logging.debug(f'send_to_topic: Reply posted successfully!')
        else:
            logging.error(f'send_to_topic: Error posting reply:',
                          response.status_code)
        return response

    @staticmethod
    def send_private_msg(subject, message):
        url = Discourse.base_url + '/posts.json'
        data = {'title': f'{subject}',
                'raw': f'{message}',
                'target_usernames': 'Geraetefreund',
                'archetype': 'private_message'}
        response = requests.post(url, headers=Discourse.headers, data=data)
        if response.status_code == 200:
            logging.debug(f'send_private_msg: Reply posted successfully!')
        else:
            logging.error(f'send_private_msg: Error posting reply:',
                          response.status_code)
        return response

    @staticmethod
    def retrieve_single_post(post_id):
        response = None
        url = Discourse.base_url + f'/posts/{post_id}.json'
        try:
            response = requests.get(url, headers=Discourse.headers)
        except Exception as error:
            logging.error(f"retrieve_single_post: {error}")
        return response

    @staticmethod
    def check_table_heading():
        response = None
        # check if the table header needs to be created  for the new month.
        welcome_table_topic_id = os.getenv('WELCOME_TABLE_TOPIC_ID')
        url = Discourse.base_url + f'/t/{welcome_table_topic_id}.json'
        try:
            response = requests.get(url, headers=Discourse.headers)
        except Exception as error:
            logging.error(f"check_table_heading: {error}")
        if response.status_code != 200:
            logging.error(f'check_table_heading: Discourse api error. {response.status_code}')
            time.sleep(2)
            response = requests.get(url, headers=Discourse.headers)

        most_recent_post_id = response.json().get('post_stream').get('stream')[-1]

        post = Discourse.retrieve_single_post(most_recent_post_id)
        raw_string = post.json().get('raw')
        search_pattern = r"# Membership invites (\w+ \d{4})"
        match = re.search(search_pattern, raw_string)
        if not match:
            """Most likely cause: Somebody replied to the slmschimp post on 
            Discourse. Naughty!"""
            logging.warning(f"Discourse.check_table_heading: No match in "
                            f"re.search. Creating new heading just to be safe.")
            Discourse.create_welcome_table_header()
            return True
        elif match:
            """This should be the default, unless somebody messed with the 
            Discourse thread. Lol."""
            date_str = match.group(1)
            date_object_found = datetime.strptime(date_str, "%B %Y")
            if datetime.now().year > date_object_found.year:
                logging.info("check_table_heading: Creating new "
                             "table heading, new year.")
                Discourse.create_welcome_table_header()
                return True
            elif datetime.now().month > date_object_found.month:
                logging.info("check_table_heading: Creating new "
                             "table heading, new month.")
                Discourse.create_welcome_table_header()
                return True
            else:
                logging.info("check_table_heading: All is good. "
                             "No need for action.")
                return False

    @staticmethod
    def create_new_post():
        url = Discourse.base_url + '/posts.json'
        now = datetime.now()
        month_year = now.strftime("%B %Y")
        raw_content = f'## SLMSchimp Logs {month_year}'
        raw_content += f'\n[details ="SLMSchimp Logs {month_year}"]\n'
        raw_content += '\n[/details]'
        data = {'topic_id': os.getenv('LOG_TOPIC_ID'),
                'raw': raw_content}
        response = requests.post(url, headers=Discourse.headers, data=data)
        if response.status_code == 200:
            logging.debug(f'create_new_post: Reply posted successfully!')
        else:
            logging.error(f'create_new_post: Error posting reply:',
                          response.status_code)
        return response

    @staticmethod
    def append_logs():
        response = None
        log_topic_id = os.getenv('LOG_TOPIC_ID')
        url = Discourse.base_url + f'/t/{log_topic_id}.json'
        try:
            response = requests.get(url, headers=Discourse.headers)
        except Exception as error:
            logging.error(f"append_logs: {error}")
        if response.status_code != 200:
            logging.error(f'append_logs: Discourse API error. {response.status_code}')
            time.sleep(2)
            response = requests.get(url, headers=Discourse.headers)
        most_recent_post_id = response.json().get('post_stream').get('stream')[-1]
        latest_log_post = Discourse.retrieve_single_post(most_recent_post_id)
        llp_raw = latest_log_post.json().get('raw')
        # let's remove the final [/details]
        if llp_raw.endswith("\n[/details]"):
            llp_raw = llp_raw[:-len("\n[/details]")]

        # let's check if we need a new reply first
        pattern = (r'(\b(?:January|February|March|April|May|June|July|August|September|October|'
                   r'November|December)\b)\s+(\d{4})')
        year_str = ''  # because IDE was moaning...
        month_num = 0
        match = re.search(pattern, llp_raw)
        if not match:
            Discourse.create_new_post()  # failsafe, in case somebody has replied to the log post, or else...
        else:
            month_str, year_str = match.groups()
            month_dict = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6, "July": 7,
                          "August": 8, "September": 9, "October": 10, "November": 11, "December": 12}
            month_num = month_dict[month_str]

        log_post_date = datetime(int(year_str), month_num, 1).date()
        today = datetime.now().replace(day=1).date()
        if log_post_date >= today:
            logging.info(f'append_logs: No action needed.')
        else:
            logging.info(f'append_logs: New month, creating new post.')
            Discourse.create_new_post()
            try:
                response = requests.get(url, headers=Discourse.headers)
            except Exception as error:
                logging.error(f"append_logs: {error}")
            if response.status_code != 200:
                logging.error(f'append_logs: Discourse API error. {response.status_code}')
                time.sleep(2)
                response = requests.get(url, headers=Discourse.headers)
            most_recent_post_id = response.json().get('post_stream').get('stream')[-1]
            latest_log_post = Discourse.retrieve_single_post(most_recent_post_id)
            llp_raw = latest_log_post.json().get('raw')
            # let's remove the final [/details]
            if llp_raw.endswith("\n[/details]"):
                llp_raw = llp_raw[:-len("\n[/details]")]

        log_date = datetime.now().strftime("%Y-%m-%d | %H:%M")
        log_entry = f'\n[details ="{log_date}"]\n'
        log_entry += '\n'.join(list_handler.log_records)
        log_entry += '\n[/details]'
        log_entry += '\n[/details]'  # twice because we've removed the final one.

        updated_log_post = llp_raw + log_entry

        # sending logs
        url = Discourse.base_url + f'/posts/{most_recent_post_id}.json'
        data = {'post': {'raw': updated_log_post,
                         'edit_reason': f'slmschimp-{datetime.now().date().isoformat()}'}}
        try:
            response = requests.put(url, headers=Discourse.headers, json=data)
        except Exception as error:
            logging.error(f'append_logs: {error}')
        return response

    @staticmethod
    def update_welcome_table(raw):
        response = None
        welcome_table_topic_id = os.getenv('WELCOME_TABLE_TOPIC_ID')
        url = Discourse.base_url + f'/t/{welcome_table_topic_id}.json'
        try:
            response = requests.get(url, headers=Discourse.headers)
        except Exception as error:
            logging.error(f"update_welcome_table: {error}")
        if response.status_code != 200:
            logging.error(f'update_welcome_table: Discourse API error. {response.status_code}')
            time.sleep(2)
            response = requests.get(url, headers=Discourse.headers)
        most_recent_post_id = response.json().get('post_stream').get('stream')[-1]

        # Now retrieve the raw content from that message and add the new bits
        post = Discourse.retrieve_single_post(most_recent_post_id)
        old_raw = post.json().get('raw')
        new_raw = old_raw + raw
        # Otherwise the old raw content will be overwritten.
        url = Discourse.base_url + f'/posts/{most_recent_post_id}.json'
        data = {'post': {'raw': new_raw,
                         'edit_reason': f'slmschimp-{datetime.now().date().isoformat()}'}}
        try:
            response = requests.put(url, headers=Discourse.headers, json=data)
        except Exception as error:
            logging.error(f"update_welcome_table: {error}")
        return response

    @staticmethod
    def create_welcome_table_header():
        """ Adds a new post to the welcome thread. Creates new table and
        header each 1st of the month."""
        response = None
        url = Discourse.base_url + '/posts.json'
        welcome_table_topic_id = os.getenv('WELCOME_TABLE_TOPIC_ID')
        table_header = "|date|name|e-mail|response-id|campaign-id|discourse-user| \n |-|-|-|-|-|-|"
        raw_content = f"# Membership invites {datetime.now().date().strftime('%B %Y')} \n"
        raw_content += table_header
        data = {'topic_id': welcome_table_topic_id,
                'raw': raw_content}
        try:
            response = requests.post(url, headers=Discourse.headers, data=data)
        except Exception as error:
            logging.error(f'crate_new_welcome_table: {error}')
        if response.status_code == 200:
            logging.debug(f'create_new_welcome_table: Reply posted successfully!')
        else:
            logging.error(f'create_new_welcome_table: Error posting reply:',
                          response.status_code)
            """ remember to get the new topic-id with response.json().get('id') """
        return response


class HouseKeeping:

    @staticmethod
    def days_till_openeve():
        """ returns int with number of days until the next open evening"""
        reference_date = datetime(2023, 7, 12).date()
        today = datetime.now().date()
        days_since_reference = (today - reference_date).days
        days_till_openeve = (14 - (days_since_reference % 14)) % 14
        return days_till_openeve

    @staticmethod
    def next_openeve():
        """ returns datetime obj with the calculated day for the next OE """
        event = datetime.now().date() + timedelta(days=HouseKeeping.days_till_openeve())
        logging.debug(f"The next Open Evening should be happening: "
                      f"{event.strftime('%A, %d %B')}")
        return event

    @staticmethod
    def do_we_have_an_event():
        event_info = Discourse.get_openeve_date_and_url()
        if event_info is None:
            logging.error(f"slmschimp: No Discourse event found in calendar.")
            return False

        event_date = event_info[0]

        if HouseKeeping.next_openeve() == event_date:
            logging.debug(f"slmschimp: We're all good. Discourse event shows:"
                          f" {event_date.strftime('%A, %d %B')}")
            return True
        elif event_date > HouseKeeping.next_openeve():
            logging.info("slmschimp: Event date lies past next calculated OE Event!")
            return True
        else:
            return False


def main():
    processed_ids = []

    if not any(vars(args).values()):
        parser.print_help()

    if args.status:
        automation.status()

    if args.auto:
        if datetime.now().date() == HouseKeeping.next_openeve():
            logging.warning("Today is Open Evening! No invitation unless "
                            "argument -f / --force is used.")
        elif args.auto and not args.force:
            if HouseKeeping.do_we_have_an_event():
                logging.debug("slmschimp: Found Discourse event for next Open"
                              " Eve. **Everything's Chimpy!**")
                processed_ids = automation.automate()
            else:
                logging.warning("slmschimp: No event for next Open Eve on "
                                "Discourse. **No Invitations will be sent** unless Discourse event is created.")

    if args.force and not args.auto:
        logging.info("slmschimp: argument -f / --force needs to be called "
                     "together with -a / --auto")

    if args.auto and args.force:
        logging.warning("automate: started with --force argument.")
        processed_ids = automation.automate()

    if args.campaign_info:
        campaign_date_and_url = automation.find_campaign_date_and_url(mc.get_campaign_content(mc.last_campaign_id()))
        last_campaign_send_time = mc.last_campaign_send_time()

        logging.info(f"Most recent campaign_id: [{mc.last_campaign_id()}]"
                     f"(https://us3.admin.mailchimp.com/reports/summary?"
                     f"id={mc.last_campaign_web_id()}). Sent: "
                     f"{last_campaign_send_time.split('T')[0]}, "
                     f"{last_campaign_send_time.split('T')[1].split('+')[0]}")
        logging.info(f"OE URL from most recent campaign: {campaign_date_and_url[1]}")
        logging.info(f"Most recent OE Discourse event: {Discourse.get_openeve_date_and_url()[1]}")

    if datetime.now().date() == HouseKeeping.next_openeve():
        logging.warning(f"Today is open evening. Campaign content and url need updating!")

    if processed_ids:
        Discourse.check_table_heading()  # check if we need a new heading for the table
        log_info = automation.collect_member_info(processed_ids)
        collected_objects = []
        for item in log_info:
            last_name = [name for name in item[1].split(' ') if name != '']
            campaign_date = f'{item[0]}'
            full_name = (f'[{item[1]}](https://southlondonmakerspace.org/wp-admin/users.php?'
                         f's={last_name[-1]})')
            email = (f'[{item[2]}](https://us3.admin.mailchimp.com/audience/contact-profile?'
                     f'contact_id={item[6]})')
            response_id = (f'[{item[3]}](https://us3.admin.mailchimp.com/lists/surveys/results?'
                           f'survey_id=3410&tab=0&response_id={item[3]}&view=INDIVIDUAL_VIEW)')
            campaign_id = (f'[{item[4]}](https://us3.admin.mailchimp.com/reports/summary?'
                           f'id={mc.last_campaign_web_id()})')
            discourse_name = f'[{item[5]}](https://discourse.southlondonmakerspace.org/u/{item[5]})'

            collected_objects.append(f'\n |{campaign_date}|{full_name}|'
                                     f'{email}|{response_id}|{campaign_id}|' f'{discourse_name}|')

        combined_raw_data = ''.join(collected_objects)
        Discourse.update_welcome_table(combined_raw_data)

    if any(vars(args).values()) and not args.quiet:
        Discourse.append_logs()


if __name__ == '__main__':
    data_provider = DataProvider()
    list_members_info = data_provider.get_list_members_info()
    if data_provider.get_total_items():
        survey_responses = data_provider.get_survey_responses()
    else:
        survey_responses = None
    mc = MailChimpAPI()
    automation = Automation(list_members_info, survey_responses)
    main()
