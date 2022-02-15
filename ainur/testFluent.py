




#======THIS FILE IS ONLY FOR DEBUG PURPOSES IN THE TESTBED======#
#-------------WILL BE REMOVED ONCE THE CODE IS STABLE-----------------#





import time
from ipaddress import IPv4Interface
from pathlib import Path

import yaml
from fluent_server import FluentServer
from fluent_client import FluentClient
from loguru import logger

#======Start Logging======#
startFresh=True #Recreate and restart container, <ONLY for development phase>

# 1. Verify that the fluent server is running. Start if it is not.
# Currently, the server is located in Galadriel. 
# TODO: Move logging to the custom Machine. It also need fluentClient Config file modification
log_dirPath="/opt/Logs/" #Note: There is a potential error in fluent in mkdir. Better make sure that the base directory exists.
print("\nStarting fluent server....")
fluentserver=FluentServer(log_dirPath)
if startFresh==True:
    fluentserver.start_fresh()
else:
    fluentserver.verify_running_status()

print("Fluent server started.\n")

# 2. Start all the Fluent clients
listOfClientNames=['finarfin','elrond','workload-client-00','workload-client-01']
# TODO: Create this list from the inventory
dockerPort='2375'
listOfClients=[]
for ClientName in listOfClientNames:
    client_url=ClientName+'.expeca:'+str(dockerPort)
    print("\nStarting fluent client in "+client_url+"....")
    fluentclient=FluentClient(client_url)
    fluentclient.remove_container()
    if startFresh==True:
        fluentclient.remove_image()
        fluentclient.create_image()
    else:
        pass
    fluentclient.start_container()
    listOfClients.append(fluentclient)
    print('Fluent client started in '+ClientName+"\n")
    #======End of logging initialisation======#