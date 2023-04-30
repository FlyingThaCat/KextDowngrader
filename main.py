import platform
import sys
import argparse
import subprocess
import plistlib
import os
import pkg_resources

# Thanks to OCLP for some of the code & Thanks To Extreme for the idea
# https://github.com/dortania/OpenCore-Legacy-Patcher/blob/main/resources/sys_patch/sys_patch.py
# https://github.com/ExtremeXT/APUDowngrader


# argparse Handler
parser = argparse.ArgumentParser(description='This Tools Will Search And Downgrade The Kext / Bundle On Your S/L/E And Even Restore It', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-i', '--input', type=str, help='Example : /Users/XXXX/Documents/new.file.kext', required=True)
parser.add_argument('-r', '--restore', help='Restore All The Kext', action='store_true')
args = parser.parse_args()
config = vars(args)

# Constants
MOUNTPATH = "/System/Volumes/Update/mnt1"
KEXTHOMEDIR = "/System/Volumes/Update/mnt1/System/Library/Extensions"

# Modules Handler
REQUIRED_MODULES = {'termcolor', 'py-sip-xnu'}
INSTALLED_MODULES = {pkg.key for pkg in pkg_resources.working_set}
MISSING_MODULES = REQUIRED_MODULES - INSTALLED_MODULES

# Script run dir
scriptDir = os.path.dirname(os.path.realpath(__file__))

def runShellCommand(command): 
    try:
        return subprocess.run(command.split(), check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return e

# Check if all modules are installed
if MISSING_MODULES:
    python = sys.executable
    print(f"{len(REQUIRED_MODULES)} Missing Modules", *MISSING_MODULES)
    print(f"Installing...")
    runShellCommand(f"{python} -m pip install {' '.join(MISSING_MODULES)}")

try:
    import py_sip_xnu
    from termcolor import cprint, colored
except:
    print("Failed to import modules! Please install them manually.")
    sys.exit()

# Colored PrintOut
errorPrint = lambda x: cprint(x, "red", attrs=["bold"])
warningPrint = lambda x: cprint(x, "yellow", attrs=["bold"])
successPrint = lambda x: cprint(x, "green", attrs=["bold"])

# Makesure To Run Only On Mac
if not sys.platform.startswith('darwin'):
    warningPrint(f"Detected :{sys.platform}")
    errorPrint(f"Please Only Run It On MacOS")
    sys.exit()
else:
    successPrint(f"Detected : MacOS {platform.mac_ver()[0]}")

# Checking Secure Boot status
if runShellCommand("nvram 94b73556-2197-4702-82a8-3e1337dafbfb:AppleSecureBootPolicy").stdout.decode().split("%")[1].strip() == '00':
    successPrint("Apple Secure Boot is Disabled! Continueing...")
else:
    warningPrint("Apple Secure Boot is enabled! It has to be turned off in order to continue.")
    warningPrint("Please set SecureBootModel to Disabled.")
    sys.exit()

# Checking SIP status
if (py_sip_xnu.SipXnu().get_sip_status().can_edit_root and py_sip_xnu.SipXnu().get_sip_status().can_load_arbitrary_kexts):
    successPrint("Compatible SIP value detected! Continueing...")
else:
    warningPrint("Your SIP value is too low! It needs to be at least 0x803.")
    warningPrint("That means csr-active-config has to be set to at least 03080000.")
    warningPrint("If this has already been done, you might also need to reset NVRAM.")
    sys.exit()

warningPrint("Please enter your password when you are asked to.")

class DiskRoot:
    def __init__(self, devicePath, mountPath):
        self.devicePath = devicePath
        self.mountPath = mountPath

    def mountDisk(self):
        try:
            runShellCommand(f"sudo /sbin/mount_apfs -R {self.devicePath} {self.mountPath}")
        except subprocess.CalledProcessError as e:
            errorPrint("Failed to mount root volume!")
            errorPrint("[Command Output] " + e.output.decode())
        successPrint("Root volume successfully mounted!")

    def unmountDisk(self):
        try:
            runShellCommand(f"sudo /sbin/umount {self.mountPath}")
        except subprocess.CalledProcessError as e:
            errorPrint("Failed to unmount root volume!")
            errorPrint("[Command Output] " + e.output.decode())
        successPrint("Root volume successfully unmounted!")

    def getRootPartition():
        rootPartition = plistlib.loads(runShellCommand("diskutil info -plist /").stdout.decode().strip().encode())["DeviceIdentifier"]
        if rootPartition.count("s") > 1:
            rootPartition = rootPartition[:-2]
        return rootPartition

# Init DiskRoot
Disk = DiskRoot(DiskRoot.getRootPartition(), MOUNTPATH)

# Unmounting Disk First
Disk.unmountDisk()

# Mounting Disk
Disk.mountDisk()

# Handling Restore
if config["restore"]:
    # Get All File From Backup Directory
    backupDir = os.path.join(scriptDir, "backup")
    
    if not os.path.exists(backupDir):
        errorPrint("Backup Directory Not Found!")
        sys.exit()
    if not os.listdir(backupDir):
        errorPrint("Backup Directory Is Empty!")
        sys.exit()

    # Get All Kext From Backup Directory
    kextList = [kext for kext in os.listdir(backupDir) if kext.endswith(".kext") or kext.endswith(".bundle")]

    # Print all kext that will be restored
    warningPrint("Kext that will be restored :")
    for kext in kextList:
        successPrint(kext)

    # Ask for confirmation
    if input("Are you sure you want to restore all kext? (y/n) : ").lower() != "y":
        sys.exit()

    # Remove All Kext From S/L/E That Has Name Same As Backup Directory
    for kext in kextList:
        kextDir = runShellCommand(f"sudo find {KEXTHOMEDIR} -name {kext}").stdout.decode().strip()
        if kextDir == "":
            warningPrint(f"Kext {kext} not found!")
        else:
            runShellCommand(f"sudo rm -rf {kextDir}")
            successPrint(f"Kext {kext} successfully removed!")
    
    # Copy All Kext From Backup Directory To S/L/E
    for kext in kextList:
        runShellCommand(f"sudo cp -R {os.path.join(backupDir, kext)} {KEXTHOMEDIR}")
        successPrint(f"Kext {kext} successfully restored!")

    # Fixing Permissions
    for kext in kextList:
        kextDir = runShellCommand(f"sudo find {KEXTHOMEDIR} -name {kext}").stdout.decode().strip()
        runShellCommand(f"sudo chmod -Rf 755 {kextDir}")
        runShellCommand(f"sudo chown -Rf root:wheel {kextDir}")
        successPrint(f"Kext {kext} successfully fixed permissions!")
    
    # Rebuilding KC
    resultKC = runShellCommand("sudo kmutil install --volume-root /System/Volumes/Update/mnt1 --update-all --variant-suffix release")
    if resultKC.returncode != 0:
        warningPrint("Failed to rebuild KC!")
        errorPrint(resultKC.stdout.decode()+"\n")
        sys.exit()
    successPrint("Successfully rebuilt KC!")

    # Create system volume snapshot
    resultBless = runShellCommand("sudo bless --folder /System/Volumes/Update/mnt1/System/Library/CoreServices --bootefi --create-snapshot")
    if resultBless.returncode != 0:
        warningPrint("Failed to create system volume snapshot!!")
        errorPrint(resultBless.stdout.decode()+"\n")
        sys.exit()
    successPrint("Successfully created a new APFS volume snapshot!")

    successPrint("Successfully restored all kexts!")
    sys.exit()

# Handling Replace
kextLocation = config["input"]

kextName = os.path.basename(kextLocation)
if not kextName.endswith(".kext") or kextName.endswith(".bundle"):
    errorPrint("Please enter a valid kext directory!")
    sys.exit()

# AutoFind Kext Directory
kextDir = runShellCommand(f"sudo find {KEXTHOMEDIR} -name {kextName}").stdout.decode().strip()
if kextDir == "":
    errorPrint("Kext not found!")
    sys.exit()

# Print Confirmation
successPrint(f"Kext Replaced Directory: {kextDir}")
successPrint(f"Kext Location: {kextLocation}")

# Ask for confirmation
if input("Are you sure you want to replace the kext? (y/n) : ").lower() != "y":
    sys.exit()

# Backing up original kexts
if not os.path.exists(f"{scriptDir}/Backups"):
    os.mkdir(f"{scriptDir}/Backups")

# If Backup Not Exists Then Create And If Exists Then Don't Create
if not os.path.exists(f"{scriptDir}/Backups/{kextName}"):
    runShellCommand(f"sudo cp -Rf {kextDir} {scriptDir}/Backups/{kextName}")
    successPrint(f"Backup of {kextName} created!")
else:
    warningPrint(f"Backup of {kextName} already exists!")

# rm -rf kext
runShellCommand(f"sudo rm -rf {kextDir}")
successPrint("Kexts successfully deleted!")

# cp -R kext
cpResult = runShellCommand(f"sudo cp -Rf {str(kextLocation)} {str(kextDir)}")
if cpResult.returncode != 0:
    errorPrint("Failed to copy kexts!")
    errorPrint("[Command Output] " + cpResult.stdout.decode())
    sys.exit()
successPrint("Kexts successfully replaced!")

# Fix permissions
runShellCommand(f"sudo chmod -Rf 755 {kextDir}")
runShellCommand(f"sudo chown -Rf root:wheel {kextDir}")
print("Kext permissions successfully fixed!")

# Rebuild KC
resultKC = runShellCommand("sudo kmutil install --volume-root /System/Volumes/Update/mnt1 --update-all --variant-suffix release")
if resultKC.returncode != 0:
    warningPrint("Failed to rebuild KC!")
    errorPrint(resultKC.stdout.decode()+"\n")
    sys.exit()
successPrint("Successfully rebuilt KC!")

# Create system volume snapshot
resultBless = runShellCommand("sudo bless --folder /System/Volumes/Update/mnt1/System/Library/CoreServices --bootefi --create-snapshot")
if resultBless.returncode != 0:
    warningPrint("Failed to create system volume snapshot!!")
    errorPrint(resultBless.stdout.decode()+"\n")
    sys.exit()
successPrint("Successfully created a new APFS volume snapshot!")

successPrint("Successfully replaced the required kexts!")
sys.exit(0)
