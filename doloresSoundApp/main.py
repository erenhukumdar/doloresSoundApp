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


class LisnrApp(object):
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
        # self.preferences.update()
        self.connect_to_preferences()
        self.create_signals()
        self.logger.info("Initialized!")

        # self.nfc_start('test')


    @qi.nobind
    def start_app(self):
        # do something when the service starts
        print "Starting app..."
        # @TODO: insert whatever the app should do to start

        # self.show_screen()
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

            # self.url_clear = self.preferences.getValue('nfc', "url_clear")
            # self.url_get = self.preferences.getValue('nfc', "url_get")
            # self.user_name = self.preferences.getValue('nfc', "user_name")
            # self.password = self.preferences.getValue('nfc', "password")
            # self.interval = int(self.preferences.getValue('nfc', "interval"))
            # self.duration = int(self.preferences.getValue('nfc', "duration"))
            # self.empty_app_id = self.preferences.getValue('global_variables', 'empty_app_id')
            # self.auth_launcher_id = self.preferences.getValue('global_variables', 'auth_launcher_id')
            # self.picture_path = self.preferences.getValue('my_friend', 'picture_path')
            self.gallery_name = self.preferences.getValue('my_friend', "gallery_name")

        except Exception, e:
            self.logger.info("failed to get preferences".format(e))
        self.logger.info("Successfully connected to preferences system")

    @qi.nobind
    def create_signals(self):
        self.logger.info("Creating ColorChosen event...")
        # When you can, prefer qi.Signals instead of ALMemory events
        memory = self.session.service("ALMemory")

        event_name = "SoundApp/Test"
        memory.declareEvent(event_name)
        event_subscriber = memory.subscriber(event_name)
        event_connection = event_subscriber.signal.connect(self.test)
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

    @qi.bind(methodName="test", returnType=qi.Void)
    def clear_all_tag_records(self):
        try:
            self.logger.info('clear works')
            response = requests.get(self.url_clear, auth=HTTPBasicAuth(self.user_name, self.password))
            return True
        except Exception, e:
            self.logger.info('Error while requesting result: {}'.format(e))
            return False

    @qi.nobind
    def get_customer_info(self):
        try:
            response = requests.get(self.url_get, auth=HTTPBasicAuth(self.user_name, self.password))
            self.logger.info(response.text)
            data = response.json()
        except Exception, e:
            self.logger.info('Error while requesting result: {}'.format(e))
            data = json.dumps({"error": "cannot find"});
        return data

    @qi.nobind
    def nfc_start(self, value):
        self.logger.info("nfc process started")
        if self.clear_all_tag_records():
            self.logger.info("phase 2")
            self.counter = 0
            response = self.nfc_check()
            # print('response arrived'+response)
            self.logger.info('response check='+str(response))

        else:
            memory = self.session.service('ALMemory')
            memory.createEvent("NFC/ClearError", 1)

    @qi.nobind
    def nfc_check(self):
        self.counter += 1
        memory = self.session.service('ALMemory')
        response = self.get_customer_info()
        self.logger.info('response customer info'+str(response))
        self.logger.info('duration'+str(self.duration))
        try:
            exit_status = memory.getData('NFC/ExitApp')
        except Exception, e:
            self.logger.error(e)
            exit_status = -1
        self.logger.info('exit status', str(exit_status))
        if exit_status == 0:
            self.logger.info('Exit selected')
            self.nfc_redirect(0)
        else:
            self.logger.info('exit not selected')
            if self.counter <= int(self.duration) and ('error' in response):
                time.sleep(0.7)
                self.logger.info("not found request failed")
                self.nfc_check()
            elif self.counter > int(self.duration / self.interval):
                self.logger.info("Timer overflow")

                memory.raiseEvent("NFC/TimeError", 1)
            else:
                if response is None:
                    time.sleep(0.7)
                    self.logger.info("not found request none")
                    self.nfc_check()
                else:
                    memory = self.session.service('ALMemory')
                    customer = CustomerQuery()
                    customer.query_customer(response[0]['customer_number'], "U")
                    self.enroll_face(customer.customer_number)
                    self.logger.info('Customer Info='+str(customer.jsonify()))
                    memory.insertData("Global/CurrentCustomer", str(customer.jsonify()))
                    memory.raiseEvent("NFC/Found", 1)
                    return response

    @qi.nobind
    def rest_mode(self, value):
        self.logger.info("rest position")
        # motion = self.session.service('ALMotion')
        # motion.rest()

    @qi.nobind
    def nfc_redirect(self, value):
        self.logger.info('redirect is working')
        memory = self.session.service('ALMemory')
        autonomous_life = self.session.service('ALAutonomousLife')
        try:
            if value == 1:
                redirect_app = str(memory.getData('Global/RedirectingApp'))
                self.logger.info("Redirection is working for="+redirect_app)
                autonomous_life.switchFocus(redirect_app)
            else:
                self.logger.info("Redirection is working for=" + self.auth_launcher_id)
                autonomous_life.switchFocus(self.auth_launcher_id)
        except Exception, e:
            self.logger.info(e)
            self.logger.error(e)
            memory = self.session.service('ALMemory')
            memory.raiseEvent('NFC/ExecutionError', 1)
            self.logger.info('error event raised')
        self.cleanup()

    @qi.nobind
    def return_to_idle(self, value):
        self.memory_cleanup()
        autonomous_life = self.session.service('ALAutonomousLife')
        autonomous_life.switchFocus(self.empty_app_id)

    @qi.nobind
    def memory_cleanup(self):
        memory = self.session.service('ALMemory')
        try:
            memory.removeData("Global/CurrentCustomer")
        except Exception, e:
            self.logger.error(e)
        try:
            memory.removeData("Global/RedirectingApp")
        except Exception, e:
            self.logger.error(e)
        try:
            memory.removeData("Global/RedirectingApp")
        except Exception, e:
            self.logger.error(e)

        try:
            memory.removeData("MyFriend/VerifiedAge")
            memory.removeData("MyFriend/LauncherForAdultKnown")
        except Exception, e:
            self.logger.error(e)

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

    @qi.bind(methodName="testSound", returnType=qi.Void)
    def test(self, value):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        lib_path = os.path.realpath(os.path.join(dir_path, "Lisnr", "PyLISNRCore.so"))
        self.logger.info(lib_path)
        my_test_lib = ctypes.cdll.LoadLibrary(lib_path)

if __name__ == "__main__":
    # with this you can run the script for tests on remote robots
    # run : python main.py --qi-url 123.123.123.123
    app = qi.Application(sys.argv)
    app.start()
    service_instance = LisnrApp(app)
    service_id = app.session.registerService(service_instance.service_name, service_instance)
    service_instance.start_app()
    app.run()
    service_instance.cleanup()
    app.session.unregisterService(service_id)
