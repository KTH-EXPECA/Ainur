import docker
import os

class FluentClient():

    def __init__(self,client_url):
        self.docker_client=docker.DockerClient(base_url=client_url)

    def prune(self):
        self.remove_image() 
        #Remove fluent images and containers.
        #self.REMOVE_VOLUEMES #Remove volumes if used. Currently only mounting existing directory is used

    def stop_container(self):
        try:
            self.docker_client.containers.get('fluentclient_container').stop()
            print('\tStopping existing fluent client containers...')
        except:
            pass

    def remove_container(self):
        self.stop_container()    #Stop Container before removing it
        try:
            self.docker_client.containers.get('fluentclient_container').remove()
            print('\tRemoving existing fluent client containers...')
        except:
            pass

    def remove_image(self):
        self.remove_container()  #Remove Container before removing the image
        try:
            self.docker_client.images.remove(image="fluentclient_image")
            print('\tRemoving fluent client Image...')
        except:
            pass

    def create_image(self):
        # pyFile_dir_path = os.path.dirname(os.path.realpath(__file__))
        # os.chdir(pyFile_dir_path)
        # self.fluentImage = self.docker_client.images.build(path = "./../Fluent/Client/", tag="fluentclient_image")
        self.fluentImage = self.docker_client.images.build(path = "/home/expeca/Ainur/Fluent/Client/", tag="fluentclient_image")
        print('\tCreated new Fluent Client Image, '+str(self.fluentImage[0])+'.')

    def start_container(self,ClientName):
        # TODO: Collect the proper workloadName/MetaData to pass on to the container. Currently "ArbitraryWorkLoad" is used
        self.docker_client.containers.run(
            image="fluentclient_image", 
            detach=True, 
	        stdin_open=True,
            tty=True,
            name="fluentclient_container",
            environment={'logName': 'ArbitraryWorkLoad','hostName':ClientName},
            ports={'24224/tcp':24224,'24224/udp':24224,'24225/tcp':24225,'24225/udp':24225}
            #,volumes=[str(self.dirPath)+str(self.dirName)+':/fluent-bit/log:rw']
        )
        print('\tStarting fluent client container...')

    def start_fresh(self,ClientName):
        self.prune()
        self.create_image()
        self.start_container(ClientName)