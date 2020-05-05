import pyeapi
from cvprac.cvp_client import CvpClient
from cvprac.cvp_client_errors import CvpApiError
#Disables no certificate CVP warning
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import json, re, csv
from getpass import getpass

def updateInCVP(cvp, name, config, serial_number, apply=True):
    '''
    Args:
        name (str) -> name of the configlet
        config (str) -> content of configlet
        serial_number (str) -> device serial number
    Returns list of taskIds if any [1, 21]
    '''
    #Attempt to get config
    try:
        configlet_exists = cvp.api.get_configlet_by_name(name)
    except:
        # print ("Configlet {} doesn't exist".format(name))
        configlet_exists = None
    #get device information from CVP
    device_dict = cvp.api.get_device_by_serial_number(serial_number)

    #initialize tasks variable
    task_ids = []
    tasks = None
    
    #Configlet does not exist
    if configlet_exists is None:
        #add new configlet to CVP
        configlet = cvp.api.add_configlet(name, config)
        # print ("Added Configlet {} to CVP".format(name))
        #get newly created configlet
        new_configlet = cvp.api.get_configlet_by_name(name)

        if apply==True:
            #Create list of configlets to apply 
            configlets_to_apply = []
            #Add configlet to list of configlets to apply
            configlets_to_apply.append(new_configlet)

            #apply configlet to device
            tasks = cvp.api.apply_configlets_to_device("Generated by deployment script", device_dict,  configlets_to_apply)

    else:
        #configlet already exists

        #check if config is in sync
        # if checkIfDeviceInSync(device_dict) != True:
        #     #If device is not in sync return None
        #     return None

        #update existing configlet
        key = configlet_exists["key"]
        tasks = cvp.api.update_configlet(config, key, name, wait_task_ids=True)
        # print ("Modified Configlet {} in CVP".format(name))

        if apply == True:

            try:
                if "taskIds" in list(tasks):
                    # print "Returning tasks for configlet {}".format(name)
                    task_ids = tasks["taskIds"]
            except:
                pass

            updated_configlet = cvp.api.get_configlet_by_name(name)
            configlets_already_applied = cvp.api.get_configlets_by_netelement_id(device_dict["key"])["configletList"]
            names_of_configlets_already_applied = []
            for configlet in configlets_already_applied:
                names_of_configlets_already_applied.append(configlet["name"])

            if updated_configlet["name"] not in names_of_configlets_already_applied:
                # print "Configlet {} is not applied".format(updated_configlet["name"])
                # print "Applying {} to {}".format(updated_configlet["name"], device_dict["hostname"])
                tasks = cvp.api.apply_configlets_to_device("Generated by deployment script", device_dict,  [updated_configlet])
                # print ("Reapplied configlet to device")

    # return tasks
    if len(task_ids) > 0:
        try:
            tasks = tasks["data"]
            if "taskIds" in list(tasks):
                # print "Returning tasks for configlet {}".format(name)
                for task in tasks["taskIds"]:
                    if task not in task_ids:
                        task_ids.append(task)
                # print ("task_ids:", task_ids)
                return task_ids
            else:
                # print "No tasks to return for configlet {}".format(name)
                # print ("task_ids:", task_ids)
                return task_ids
        except:
            # print ("task_ids:", task_ids)
            return task_ids
    else:
        try:
            tasks = tasks["data"]
            if "taskIds" in list(tasks):
                # print "Returning tasks for configlet {}".format(name)
                # print ("task_ids:", task_ids)
                return tasks["taskIds"]
            else:
                # print "No tasks to return for configlet {}".format(name)
                # print ("task_ids:", task_ids)
                return []
        except:
            return []

def deploy_device_with_no_configlets(cvp, device_dict, target_container, mgmt_configlet_name):
    '''
        Creates a static configlet of the reconcile config produced as if no configlets are applied to the device
        Then deploys device into proper container based off of first three characters of device hostname and applies previously generated configlet
    '''
    configlets_to_generate_reconcile = []
    configlets_to_apply = []
    if device_dict["streamingStatus"] == "inactive":
        print("{} - Device is not streaming data to CVP".format(device_dict["hostname"]))
        return
    #get device information from CVP
    print("{} - Getting device information...".format(device_dict["hostname"]))
    # print "Device"
    # print json.dumps(device_dict)
    # print "\n\n"
    device_id = device_dict["systemMacAddress"]
    
    # print "Configlets"
    # print json.dumps(configlets)
    # print "\n\n"

    print("{} - Got device information".format(device_dict["hostname"]))

    #keys of configlets we'll pretend are applied to a device when we generate a reconcile config
    container_configlet_keys = [ configlet["key"] for configlet in cvp.api.get_configlets_inherited_from_containers(target_container) ]
    configlets_to_generate_reconcile = container_configlet_keys
    try:
        mgmt_configlet = cvp.api.get_configlet_by_name(mgmt_configlet_name)
    except:
        mgmt_configlet = None
    if mgmt_configlet is not None:
        configlets_to_generate_reconcile.append(mgmt_configlet["key"])
        configlets_to_apply.append(mgmt_configlet)

    #Generate consolidated configlet
    print ("{} - Generating configlet configuration...".format(device_dict["hostname"]))
    validate_response = cvp.api.validate_configlets_for_device(device_id, configlets_to_generate_reconcile,
                                       page_type='viewConfig')

    if "config" in validate_response["reconciledConfig"].keys():
        config = validate_response["reconciledConfig"]["config"]
    else:
        print("{} - No reconcile configlet to generate.".format(device_dict["hostname"]))
        return

    #Create and apply consolidated configlet
    configlet_name = device_dict["hostname"]

    #Create New Configlet
    print ("{} - Updating/Creating configlet...".format(device_dict["hostname"]))
    tasks =  updateInCVP(cvp, configlet_name, config, device_dict["serialNumber"], apply=False)
    print ("{} - Updated/Created configlet".format(device_dict["hostname"]))

    try:
        configlet_to_apply = cvp.api.get_configlet_by_name(configlet_name)
    except CvpApiError as e:
        configlet_to_apply = None

    if configlet_to_apply is not None:
        configlets_to_apply.append(configlet_to_apply)
    else:
        print("{} - Could not find configlet named {}".format(configlet_name, device_dict["hostname"]))
        return

    if cvp.api.get_container_by_name(target_container) is None:
        print("{} - Could not find destination container for {}".format(device_dict["hostname"], device_dict["hostname"]))
        return

    # print("Device ID -> {}".format(device_dict))
    # print("Target container -> {}".format(target_container))
    # print("Configlets to apply -> {}".format(configlets_to_apply))

    cvp.api.deploy_device(device_dict, target_container, configlets=configlets_to_apply)

    return

def create_mgmt_configlet(cvp, hostname, mgmt_interface, mgmt_ip, default_gateway, mgmt_vrf="default"):
    #Give name to management configlet
    configlet_name = hostname + "_MGMT"
    #Create configuration for managment configlet
    configlet_content = []
    configlet_content.append("hostname {}".format(hostname))
    configlet_content.append("!")
    if mgmt_vrf is not None and mgmt_vrf != "default":
        configlet_content.append("vrf instance {}".format(mgmt_vrf))
        configlet_content.append("   rd 1:1")
        configlet_content.append("!")
    configlet_content.append("interface {}".format(mgmt_interface))
    if mgmt_vrf is not None and mgmt_vrf != "default":
        configlet_content.append("   vrf {}".format(mgmt_vrf))
    configlet_content.append("   ip address {}".format(mgmt_ip))
    configlet_content.append("!")
    if mgmt_vrf is not None and mgmt_vrf != "default":
        configlet_content.append("ip route vrf {} 0.0.0.0/0 {}".format(mgmt_vrf, default_gateway))
    else:
        configlet_content.append("ip route 0.0.0.0/0 {}".format(default_gateway))
    configlet_content.append("!")
    configlet_content.append("ip routing")
    if mgmt_vrf is not None and mgmt_vrf != "default":
        configlet_content.append("no ip routing vrf {}".format(mgmt_vrf))
    configlet_content.append("!")
    configlet_content.append("management api http-commands")
    configlet_content.append("   no shutdown")
    if mgmt_vrf is not None and mgmt_vrf != "default":
        configlet_content.append("   !")
        configlet_content.append("   vrf {}".format(mgmt_vrf))
        configlet_content.append("      no shutdown")
    configlet_content.append("!")
    configlet_content = "\n".join(configlet_content)
    #Create/Update Configlet in CVP
    try:
        existing_mgmt_configlet = cvp.api.get_configlet_by_name(configlet_name)
    except Exception:
        existing_mgmt_configlet = None
    if existing_mgmt_configlet is None:
        cvp.api.add_configlet(configlet_name, configlet_content)
    else:
        cvp.api.update_configlet(configlet_content, existing_mgmt_configlet["key"], configlet_name)
    return configlet_name

def parse_switch_info_file(switch_info_file):
    switches = {} #Using serial number as key
    with open(switch_info_file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                attributes = [attr.strip() for attr in row ] 
                line_count += 1
            else:
                switch_info = {}
                for col in range(len(attributes)):
                    switch_info[attributes[col]] = row[col]
                switches[switch_info["Hostname"]] = {
                    "Management VRF": switch_info["Management VRF"],
                    "Target Container": switch_info["Target Container"],
                    "Default Gateway": switch_info["Default Gateway"],
                    "IP Address": switch_info["Management IP Address"]
                }
                line_count += 1
    return switches

def get_mgmt_switch_info(ip_address, username, password, mgmt_vrf="default"):
    switch = pyeapi.connect(host=ip_address, username=username, password=password)
    if mgmt_vrf != "default":
        management_interface_config = switch.execute(["show ip route vrf {} 0.0.0.0/0".format(mgmt_vrf)])["result"][0]
    else:
        management_interface_config = switch.execute(["show ip route 0.0.0.0/0"])["result"][0]
    if len(management_interface_config["vrfs"][mgmt_vrf]["routes"]["0.0.0.0/0"]["vias"]) > 0:
        mgmt_gateway = management_interface_config["vrfs"][mgmt_vrf]["routes"]["0.0.0.0/0"]["vias"][0]["nexthopAddr"]
        mgmt_interface = management_interface_config["vrfs"][mgmt_vrf]["routes"]["0.0.0.0/0"]["vias"][0]["interface"]
    else:
        mgmt_gateway = None
        mgmt_interface = None
    
    if mgmt_interface is not None:
        mgmt_interface = "Management 1"
    
    interface_config = switch.execute(["show interfaces {}".format(mgmt_interface)])["result"][0]
    if len(interface_config["interfaces"][mgmt_interface.replace(" ", "")]["interfaceAddress"]) > 0:
        mgmt_address_ip = interface_config["interfaces"][mgmt_interface.replace(" ", "")]["interfaceAddress"][0]["primaryIp"]["address"]
        mgmt_address_mask = interface_config["interfaces"][mgmt_interface.replace(" ", "")]["interfaceAddress"][0]["primaryIp"]["maskLen"]
        mgmt_address = mgmt_address_ip + "/" + str(mgmt_address_mask)
    else:
        mgmt_address = None
    
    return {"Management Interface": mgmt_interface, "Management IP Address": mgmt_address, "Default Gateway": mgmt_gateway}


def main():
    switch_info_dict = parse_switch_info_file("switch_mgmt_details.csv")
    username = "cvpadmin"
    password = getpass("Password:")
    cvp_addresses = ["10.20.30.185"]
    cvp = CvpClient()
    cvp.connect(cvp_addresses, username, password)
    inventory = cvp.api.get_devices_in_container("Undefined")
    for switch in inventory:
        #Check to see if switch in spreadsheet and get VRF 
        try:
            switch_details = switch_info_dict[switch["hostname"]]
        except KeyError:
            print("Could not find {}'s serial number in spreadsheet".format(switch["hostname"]))
            continue

        #Parse switch details
        target_container = switch_details["Target Container"]# "DC2-Leafs"#Get target container
        mgmt_interface = "Management1" 
        mgmt_ip = switch_details["Management IP Address"]    # switch["ipAddress"] + "/24"
        default_gateway = switch_details["Default Gateway"] # "10.20.30.254"
        mgmt_vrf = switch_details["Management VRF"]   # "MGMT"

        management_configlet_name = create_mgmt_configlet(cvp, switch["hostname"], mgmt_interface, mgmt_ip,
                                                            default_gateway, mgmt_vrf=mgmt_vrf)

        deploy_device_with_no_configlets(cvp, switch, target_container, management_configlet_name)
        break

if __name__ == "__main__":
    main()