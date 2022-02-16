import datetime
import docker
import os

class FluentServer():

    def __init__(self,log_dirPath):
        self.docker_server = docker.from_env()
        self.dirName=datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-UTC")
        self.dirPath=log_dirPath

    def prune(self):
        self.remove_image() 
        #Remove fluent images and containers.
        #self.REMOVE_VOLUEMES #Remove volumes if used. Currently only mounting existing directory is used

    def stop_container(self):
        try:
            self.docker_server.containers.get('fluentserver_container').stop()
            print('\tStopping existing fluent server containers...')
        except:
            pass

    def remove_container(self):
        self.stop_container()    #Stop Container before removing it
        try:
            self.docker_server.containers.get('fluentserver_container').remove()
            print('\tRemoving existing fluent server containers...')
        except:
            pass

    def remove_image(self):
        self.remove_container()  #Stop (And Remove) Container before removing the image
        try:
            self.docker_server.images.remove(image="fluentserver_image")
            print('\tRemoving fluent server Image...')
        except:
            pass

    # # =====Create fresh images and containers
    # # After code stabilisation, removal/recreation can be ignored  to save time.===
    def create_image(self):
        # pyFile_dir_path = os.path.dirname(os.path.realpath(__file__))
        # os.chdir(pyFile_dir_path)
        # self.fluentImage = self.docker_server.images.build(path = "./../Fluent/Server/", tag="fluentserver_image")
        self.fluentImage = self.docker_server.images.build(path = "/home/expeca/Ainur/Fluent/Server/", tag="fluentserver_image")
        print('\tCreated Fluent Server Image, '+str(self.fluentImage[0])+'.')

    def start_container(self):
        self.docker_server.containers.run(
            image="fluentserver_image", 
            detach=True, 
            name="fluentserver_container",
            ports={'24225/tcp':24225,'24225/udp':24225}, # 24224/tcp':24224,'24224/udp':24224},
            volumes=[str(self.dirPath)+str(self.dirName)+':/fluent-bit/log:rw']
        )
        print('\tStarting fluent server container...')

    def start_fresh(self):
        self.prune()
        self.create_image()
        self.start_container()

    def verify_running_status(self):
        try:
            self.docker_server.containers.get('fluentserver_container').start()
            print('\tFluent server container is running.')
        except:   
            self.prune()
            self.create_image()
            self.start_container()
            print('\tNo running/stopped fluent Server container found. Creating new image and starting the container...')
