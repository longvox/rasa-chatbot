# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/core/actions/#custom-actions/


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.forms import FormAction, REQUESTED_SLOT
import asyncio
import re
import pika
import uuid
# from rasa.core.brokers.pika import PikaEventBroker
# from rasa.core.tracker_store import InMemoryTrackerStore

# pika_broker = PikaEventBroker('localhost',
#                               'guest',
#                               'guest',
#                               queues=['rasa_events'])

# tracker_store = InMemoryTrackerStore(
#     domain="localhost", event_broker=pika_broker)


class BotEvent(object):
    def __init__(self):
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='localhost'))

        self.channel = self.connection.channel()

        result = self.channel.queue_declare(queue='', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, message):
        self.response = None
        self.corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key='bot_event',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=str(message))
        # while self.response is None:
        # self.connection.process_data_events()
        return self.response


bot_event = BotEvent()


def get_dict_certain_keys(dic, keys):
    return dict(
        zip(
            keys, [dic[key] for key in keys]
        )
    )


class action_get_name(Action):

    def name(self) -> Text:
        return "action_get_name"

    def run(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        print(tracker.slots)
        print(tracker.latest_message['text'])
        name = tracker.latest_message['text'].split(' ')[-1]

        return [SlotSet("name", name)]


class InfoForm(FormAction):

    def name(self) -> Text:
        return "info_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        """A list of required slots that the form has to fill"""

        return ["email", "phone"]

    @staticmethod
    def valid_email(email):
        return bool(re.search(r"[a-zA-Z0-9_.+]+@[a-zA-Z]+[.][a-zA-Z0-9-.]+$", email))

    @staticmethod
    def valid_phone(phone):
        return bool(re.search(r"^(\+\d{1,2}\s?)?1?\-?\.?\s?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$", phone))

    def validate(self,
                 dispatcher: CollectingDispatcher,
                 tracker: Tracker,
                 domain: Dict[Text, Any]) -> List[Dict]:
        """Validate extracted requested slot
            else reject the execution of the form action
        """
        # extract other slots that were not requested
        # but set by corresponding entity
        slot_values = get_dict_certain_keys(
            tracker.slots, self.required_slots(tracker))

        # extract requested slot
        slot_to_fill = tracker.get_slot(REQUESTED_SLOT)
        if slot_to_fill:
            slot_values.update(self.extract_requested_slot(dispatcher,
                                                           tracker, domain))
            if not slot_values:
                # reject form action execution
                # if some slot was requested but nothing was extracted
                # it will allow other policies to predict another action
                raise ActionExecutionRejection(self.name(),
                                               "Failed to validate slot {0} "
                                               "with action {1}"
                                               "".format(slot_to_fill,
                                                         self.name()))

        is_valid = True
        for slot, value in slot_values.items():
            if slot == 'email':
                if not self.valid_email(value.lower()):
                    dispatcher.utter_template(
                        'utter_input_email_again', tracker)
                    is_valid = False
                    break

            elif slot == 'phone':
                if not self.valid_phone(value.lower()):
                    dispatcher.utter_template(
                        'utter_input_phone_again', tracker)
                    is_valid = False
                    break

        if is_valid:
            dispatcher.utter_template('utter_submit', tracker)

        return []

    async def submit(self,
                     dispatcher: CollectingDispatcher,
                     tracker: Tracker,
                     domain: Dict[Text, Any]) -> List[Dict]:
        """Define what the form has to do
            after all required slots are filled"""
        # print(tracker.current_state())
        # utter submit template
        # dispatcher.utter_template('utter_submit', tracker)
        print(tracker.slots)
        email = tracker.slots["email"]
        phone = tracker.slots["phone"]
        bot_event.call({"email": email, "phone": phone})
        return []
