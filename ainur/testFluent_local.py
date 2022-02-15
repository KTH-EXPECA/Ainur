




#======THIS FILE IS ONLY FOR DEBUG PURPOSES IN THE LOCAL MACHINE======#
#-------------WILL BE REMOVED ONCE THE CODE IS STABLE-----------------#







from fluent_server import FluentServer
from fluent_client import FluentClient

#======Start Logging======#
server_rebuildAndRecreate=True #Recreate image & container and restart container, <ONLY for development phase>
client_rebuildAndRecreate=True 

# 1. Verify that the fluent server is running. Start if it is not.
# Currently, the server is located in Galadriel. 
# TODO: Move logging to the custom Machine. It also need fluentClient Config file modification
log_dirPath="/opt/Logs/" #Note: There is a potential error in fluent in mkdir. Better make sure that the base directory exists.
log_dirPath="/Users/vnmo/Documents/Python/Logs"
print("initialising server...........")
fluentserver=FluentServer(log_dirPath)
print("initialised.")
if server_rebuildAndRecreate==False:
    print("starting server container fresh...........")
    fluentserver.start_fresh()
else:
    fluentserver.verify_running_status()
print("server container is Running.")

# 2. Start all the Fluent clients
listOfClientNames=['finarfin','elrond','workload-client-00','workload-client-01']
# TODO: Create this list from the inventory
dockerPort='2375'
listOfClients=[]
for ClientName in listOfClientNames:
    client_url=ClientName+'.expeca:'+str(dockerPort)
    client_url='130.237.53.70:2375'
    fluentclient=FluentClient(client_url)
    fluentclient.remove_container
    if client_rebuildAndRecreate==True:
        fluentclient.remove_image
        fluentclient.create_image
    else:
        pass
    fluentclient.start_container
    listOfClients.append(fluentclient)
    #======End of logging initialisation======#