#!/usr/bin/env python

import sys
import time
import json
import datetime
import qi
import os
from customerquery import CustomerQuery
import requests
from requests.auth import HTTPBasicAuth
from kairos_face import enroll
import ctypes
from chirpsdk import chirpsdk


class ChirpApp(object):
    subscriber_list = []
    loaded_topic = ""
    counter = 0

    def __init__(self, application):
        # Getting a session that will be reused everywhere

        self.application = application
        self.session = application.session
        self.service_name = self.__class__.__name__

        # Getting a logger. Logs will be in /var/log/naoqi/servicemanager/{application id}.{service name}
        self.logger = qi.Logger(self.service_name)

        # Do some initializations before the service is registered to NAOqi
        self.logger.info("Initializing...")
        # @TODO: insert init functions here

        self.preferences = self.session.service("ALPreferenceManager")
        self.preferences.update()
        self.connect_to_preferences()
        self.create_signals()
        self.logger.info("Initialized!")
        self.create_sound()
        self.memory = self.session.service('ALMemory')
        # self.nfc_start('test')


    @qi.nobind
    def start_app(self):
        # do something when the service starts
        print "Starting app..."
        # @TODO: insert whatever the app should do to start

        self.show_screen()
        # ToDo: reactivate cleanup code
        self.start_dialog()
        self.logger.info("Started!")

    @qi.nobind
    def stop_app(self):
        # To be used if internal methods need to stop the service from inside.
        # external NAOqi scripts should use ALServiceManager.stopService if they need to stop it.
        self.logger.info("Stopping service...")
        self.application.stop()
        self.logger.info("Stopped!")

    @qi.nobind
    def cleanup(self):
        # called when your module is stopped
        self.logger.info("Cleaning...")
        # @TODO: insert cleaning functions here
        self.stop_dialog()
        self.hide_screen()
        self.disconnect_signals()
        self.logger.info("Cleaned!")


    @qi.nobind
    def connect_to_preferences(self):
        # connects to cloud preferences library and gets the initial prefs
        try:

            self.file_path = self.preferences.getValue('sound_auth', "file_path")
            self.file_name = self.preferences.getValue('sound_auth', "file_name")
            self.robot_id = self.preferences.getValue('global_variables', "robot_id")
            self.chirp_api_key = self.preferences.getValue('sound_auth', "chirp_api_key")
            self.chirp_secret_key = self.preferences.getValue('sound_auth', "chirp_secret_key")
            self.duration = int(self.preferences.getValue('sound_auth', "duration"))
            self.repetition = int(self.preferences.getValue('sound_auth', "repetition"))
            self.empty_app_id = self.preferences.getValue('global_variables', 'empty_app_id')
            self.auth_launcher_id = self.preferences.getValue('global_variables', 'auth_launcher_id')
            self.url_get = self.preferences.getValue('sound_auth', 'url_get')
            self.username = self.preferences.getValue('sound_auth', "username")
            self.password = self.preferences.getValue('sound_auth', "password")
            self.picture_path = self.preferences.getValue('my_friend', 'picture_path')
            self.gallery_name = self.preferences.getValue('my_friend', "gallery_name")

        except Exception, e:
            self.logger.info("failed to get preferences".format(e))
        self.logger.info("Successfully connected to preferences system")

    @qi.nobind
    def create_signals(self):
        self.logger.info("Creating ColorChosen event...")
        # When you can, prefer qi.Signals instead of ALMemory events
        memory = self.session.service("ALMemory")

        event_name = "SoundAuth/PlaySound"
        memory.declareEvent(event_name)
        event_subscriber = memory.subscriber(event_name)
        event_connection = event_subscriber.signal.connect(self.play_sound)
        self.subscriber_list.append([event_subscriber, event_connection])

        event_name = "SoundAuth/ExitApp"
        memory.declareEvent(event_name)
        event_subscriber = memory.subscriber(event_name)
        event_connection = event_subscriber.signal.connect(self.exit_app)
        self.subscriber_list.append([event_subscriber, event_connection])

        event_name = "SoundAuth/Redirect"
        memory.declareEvent(event_name)
        event_subscriber = memory.subscriber(event_name)
        event_connection = event_subscriber.signal.connect(self.sound_redirect)
        self.subscriber_list.append([event_subscriber, event_connection])

        self.logger.info("Event created!")

    @qi.nobind
    def disconnect_signals(self):
        self.logger.info("Unsubscribing to all events...")
        for sub, i in self.subscriber_list:
            try:
                # self.logger.info("Event name: {}".format(self.subscriber_list(i)))
                sub.signal.disconnect(i)
            except Exception, e:
                self.logger.info("Error unsubscribing: {}".format(e))
                pass
        self.logger.info("Unsubscribe done!")

    @qi.nobind
    def start_dialog(self):
        self.logger.info("Loading dialog")
        dialog = self.session.service("ALDialog")
        dir_path = os.path.dirname(os.path.realpath(__file__))
        topic_path = os.path.realpath(os.path.join(dir_path, "listen_code", "listen_code_enu.top"))
        self.logger.info("File is: {}".format(topic_path))
        self.loaded_topic = dialog.loadTopic(topic_path)
        dialog.activateTopic(self.loaded_topic)
        dialog.subscribe(self.service_name)
        dialog.gotoTag('startSoundAuth', 'listen_code')
        self.logger.info("Dialog loaded!")
        # dialog.gotoTag("cmStart", "CM")

    @qi.nobind
    def stop_dialog(self):
        self.logger.info("Unloading dialog")
        try:
            dialog = self.session.service("ALDialog")
            dialog.unsubscribe(self.service_name)
            dialog.deactivateTopic(self.loaded_topic)
            dialog.unloadTopic(self.loaded_topic)
            self.logger.info("Dialog unloaded!")
        except Exception, e:
            self.logger.info("Error while unloading dialog: {}".format(e))

    @qi.nobind
    def show_screen(self):
        folder = os.path.basename(os.path.dirname(os.path.realpath(__file__)))
        self.logger.info("Loading tablet page for app: {}".format(folder))
        try:
            self.ts = self.session.service("ALTabletService")
            self.ts.loadApplication(folder)
            self.ts.showWebview()
            self.logger.info("Tablet loaded!")
        except Exception, e:
            self.logger.info("Error while loading tablet: {}".format(e))

    @qi.nobind
    def hide_screen(self):
        self.logger.info("Unloading tablet...")
        try:
            tablet = self.session.service("ALTabletService")
            tablet.hideWebview()
            self.logger.info("Tablet unloaded!")
        except Exception, e:
            self.logger.info("Error while unloading tablet: {}".format(e))

    @qi.nobind
    def get_customer_info(self):
        try:
            payload={
                'robotId':self.robot_id
            }
            headers = {
                'Content-type': 'application/json',
                'Accept': 'text/plain',
            }
            response = requests.post(self.url_get, data=json.dumps(payload), headers=headers, auth=HTTPBasicAuth(self.username, self.password))
            self.logger.info(response.text)
            if response.status_code == 200:
                data = response.json()
                customer = CustomerQuery()
                customer.query_customer(data[0]['customerId'], "U")
                self.enroll_face(customer.customer_number)
                self.logger.info('Customer Info=' + str(customer.jsonify()))
                self.memory.insertData("Global/CurrentCustomer", str(customer.jsonify()))
                return True
            else:
                return False
        except Exception, e:
            self.logger.info('Error while requesting result: {}'.format(e))
            return False

    @qi.nobind
    def auth_check(self):
        self.logger.info("check started repetition = " + str(self.repetition))
        for x in range(1, self.repetition):
            if self.get_customer_info():
                self.logger.info('found')
                self.memory.raiseEvent("SoundAuth/Found", 1)
                # self.enroll_face()
                break
            else:
                if x % 5 == 0:
                    self.play_sound("0")
                self.logger.info('step = ' + str(x))
                time.sleep(1)

        # self.logger.info('final count='+str(x))
        if x == (self.repetition-1):
            self.logger.info('time error')
            self.memory.raiseEvent("SoundAuth/TimeError", 1)



    @qi.nobind
    def rest_mode(self, value):
        self.logger.info("rest position")
        # motion = self.session.service('ALMotion')
        # motion.rest()

    @qi.nobind
    def sound_redirect(self, value):
        self.logger.info('redirect is working')
        autonomous_life = self.session.service('ALAutonomousLife')
        try:
            if value == "1":
                redirect_app = str(self.memory.getData('Global/RedirectingApp'))
                self.logger.info("Redirection is working for="+redirect_app)
                autonomous_life.switchFocus(redirect_app)
            else:
                self.logger.info("Redirection is working for=" + self.auth_launcher_id)
                autonomous_life.switchFocus(self.auth_launcher_id)
        except Exception, e:
            self.logger.info(e)
            self.logger.error(e)
            self.memory.raiseEvent('SoundAuth/ExecutionError', 1)
            self.logger.info('error event raised')
        self.cleanup()

    @qi.nobind
    def exit_app(self, value):
        self.sound_redirect(0)

    @qi.nobind
    def return_to_idle(self, value):
        # self.memory_cleanup()
        autonomous_life = self.session.service('ALAutonomousLife')
        autonomous_life.switchFocus(self.empty_app_id)

    # @qi.nobind
    # def memory_cleanup(self):
    #     memory = self.session.service('ALMemory')
    #     try:
    #         memory.removeData("Global/CurrentCustomer")
    #     except Exception, e:
    #         self.logger.error(e)
    #     try:
    #         memory.removeData("Global/RedirectingApp")
    #     except Exception, e:
    #         self.logger.error(e)
    #     try:
    #         memory.removeData("Global/RedirectingApp")
    #     except Exception, e:
    #         self.logger.error(e)
    #
    #     try:
    #         memory.removeData("MyFriend/VerifiedAge")
    #         memory.removeData("MyFriend/LauncherForAdultKnown")
    #     except Exception, e:
    #         self.logger.error(e)

    @qi.nobind
    def enroll_face(self, value):

        try:
            picture_path = self.picture_path
            self.logger.info('enroll known face has been worked')
            self.logger.info(picture_path)
            response = enroll.enroll_face(file=picture_path, gallery_name=self.gallery_name, subject_id=value)
            self.logger.info('Response:' + str(response))
            self.logger.info(str(datetime.now()) + 'response arrived')
            status = response['images'][0]['transaction']['status']
            self.logger.info('response status=' + status)

        except Exception, e:
            self.logger.error(e)


    @qi.nobind
    def create_sound(self):
        sdk = chirpsdk.ChirpSDK(self.chirp_api_key, self.chirp_secret_key)
        chirp = sdk.create_chirp({
            "robotId": self.robot_id
        })
        self.logger.info('sound has been created with ' + chirp.identifier)
        sdk.save_wav(chirp, filename=self.file_path+self.file_name, offline=False)

    @qi.nobind
    def play_sound(self, value):
        audio = self.session.service('ALAudioPlayer')
        audio.playFile(self.file_path+self.file_name, 1.0, 0.0)
        if value == "1":
            self.logger.info('first time run')
            self.auth_check()


if __name__ == "__main__":
    # with this you can run the script for tests on remote robots
    # run : python main.py --qi-url 123.123.123.123
    app = qi.Application(sys.argv)
    app.start()
    service_instance = ChirpApp(app)
    service_id = app.session.registerService(service_instance.service_name, service_instance)
    service_instance.start_app()
    app.run()
    service_instance.cleanup()
    app.session.unregisterService(service_id)
