# Onboarding Existing Devices/Consolidate Device-Level Configlets

- [Description](#description)
- [Executing Script](#executing-script)
  - [Script Options](#script-options)
  - [Inventory File](#inventory-file)
- [Workflow](#workflow)
  - [Onboard Devices](#onboard-devices)
  - [Consolidate Device-Level Configlets](#consolidate-device-level-configlets)

## Description
This script utilizes CVP's REST API to set devices up in CVP's Provisioning page by either:

1.  Moving devices currently in the Undefined container that already have a finished running-configuration to an assigned destination container. 
2.  Consolidating any device-level configlets into one single device-level configlet


## Executing Script
To execute the script, navigate to the directory the `main.py` file is and execute the following command:
```python main.py --user <username> --password <password> --cvp <cvp-ip-address> --inventory <path-to-inventory-file>```

### Script Options
```
usage: main.py [-h] [-u USER] [-p PASSWORD] [-i INVENTORY] [-host CVP]

Provisions devices in CVP

optional arguments:
  -h, --help            show this help message and exit
  -u USER, --user USER  Username for CVP user
  -p PASSWORD, --password PASSWORD
                        Password for CVP user
  -i INVENTORY, --inventory INVENTORY
                        Path to switch management details file
  -host CVP, --cvp CVP  CVP node IP Addresses separated by commas
```

- Note that if you do not wish to enter a password value in plain text, you may leave the password field out of the initial execution command and will be prompted for it when the script is executing.

### Inventory File
The inventory file is a CSV file with headers 'Hostname', Target Container', and 'Image Bundle'.

The 'Image Bundle' header is required but entries do not require an 'Image Bundle' value.

## Workflow

1.  Script gets inventory of devices registered to CVP.
2.  For each device in the CVP inventory, the script checks to see if that device is in the CSV file based on the device hostname.  If the device is present in the spreadsheet, the script continues to process the switch.
3.  The script checks to see if the device is streaming to CVP.  If so, the script continues to process the switch.
4.  A configlet named the <hostname> of the device containing all device-level configuration (and no configuration that would be inherited from containers) is created/updated in CVP.
5.  The script will then either onboard devices by moving them out of the Undefined container to their target container defined in the CSV file or simply apply the consolidated configlet.

### Onboard Devices

1.  The script will check to see if the 'Target Container' is valid.
2.  The script will check to see if the 'Image Bundle' is valid.
3.  The script will create an 'Add Device' task using the device-level configlet, target container, and image bundle.

### Consolidate Device-Level Configlets

1.  The script will create an 'Update Config' task by removing any configlets applied to the device.
2.  The script will update that 'Update Config' task by applying the device-level configlet to the device.

