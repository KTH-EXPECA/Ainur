import datetime
import docker

class FluentServer():

    def __init__(self,log_dirPath):
        self.docker_server = docker.from_env()
        self.dirName=datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-UTC")
        self.dirPath=log_dirPath

    def prune_fluent(self):
        self.remove_fluent_image(self) 
        #Remove fluent images and containers.
        #self.REMOVE_VOLUEMES #Remove volumes if used. Currently only mounting existing directory is used

    def stop_fluent_container(self):
        try:
            self.docker_server.containers.get('fluentserver_container').stop()
            print('Stopping existing fluent server containers')
        except:
            pass

    def remove_fluent_container(self):
        self.stop_fluent_container(self)    #Stop Container before removing it
        try:
            self.docker_server.containers.get('fluentserver_container').remove()
            print('Removing existing fluent server containers')
        except:
            pass

    def remove_fluent_image(self):
        self.remove_fluent_container(self)  #Remove Container before removing the image
        try:
            self.docker_server.images.remove(image="fluentserver_image")
            print('Removing fluent server Image')
        except:
            pass


        # # =====Create fresh images and containers. 
        # # After code stabilisation, removal/recreation can be ignored  to save time.=====



    def create_image(self):
        self.fluentImage = self.docker_server.images.build(path = "./../FluentServer/", tag="fluentserver_image")
        print('Created Fluent Image, '+str(self.fluentImage[0]))

    def start_container(self):
        self.docker_server.containers.run(
            image="fluentserver_image", 
            detach=True, 
            name="fluentserver_container",
            ports={'24224/tcp':24224,'24224/udp':24224,
                '24225/tcp':24225,'24225/udp':24225},
            volumes=[str(self.dirPath)+str(self.dirName)+':/fluent-bit/log:rw'])
        print('Created fluent server container')

    def start_fresh(self):
        self.prune_fluent(self)
        self.create_image(self)
        self.start_container(self)
