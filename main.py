import platform
import sys
import subprocess
import plistlib
import os
import pkg_resources

# Thanks to OCLP for some of the code & Thanks To Extreme for the idea
# https://github.com/dortania/OpenCore-Legacy-Patcher/blob/main/resources/sys_patch/sys_patch.py
# https://github.com/ExtremeXT/APUDowngrader

# Modules Handler
REQUIRED_MODULES = {'termcolor', 'py-sip-xnu'}
INSTALLED_MODULES = {pkg.key for pkg in pkg_resources.working_set}
MISSING_MODULES = REQUIRED_MODULES - INSTALLED_MODULES

def runShellCommand(command): 
    try:
        return subprocess.run(command.split(), check=True)
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
    warningPrint(f"Detected : {sys.platform}")
    errorPrint(f"Please Only Run It On MacOS")
    # sys.exit()
else:
    successPrint(f"Detected : {platform.mac_ver()[0]}")

warningPrint("Please enter your password when you are asked to.")

class DiskRoot:
    def __init__(self, devicePath, mountPath):
        self.devicePath = devicePath
        self.mountPath = mountPath

    def mountDisk(devicePath, mountPath):
        try:
            runShellCommand(f"sudo /sbin/mount_apfs -R {devicePath} {mountPath}")
        except subprocess.CalledProcessError as e:
            errorPrint("Failed to mount root volume!")
            errorPrint("[Command Output] " + e.output.decode())
        print("Root volume successfully mounted!")

    def unmountDisk(mountPath):
        try:
            runShellCommand(f"sudo /sbin/umount {mountPath}")
        except subprocess.CalledProcessError as e:
            errorPrint("Failed to unmount root volume!")
            errorPrint("[Command Output] " + e.output.decode())
        print("Root volume successfully unmounted!")

    def getRootPartition():
        rootPartition = plistlib.loads(subprocess.run("diskutil info -plist /".split(), stdout=subprocess.PIPE).stdout.decode().strip().encode())["DeviceIdentifier"]
        if rootPartition.count("s") > 1:
            rootPartition = rootPartition[:-2]
        return rootPartition

# Init DiskRoot
Disk = DiskRoot(DiskRoot.getRootPartition(), "/System/Volumes/Update/mnt1")

# Unmounting Disk First
Disk.unmountDisk(Disk.mountPath)

# Mounting Disk
Disk.mountDisk(Disk.devicePath, Disk.mountPath)

# Ask Kext Dir To Replace
kextDir = colored(input("Please Enter The Kext Directory To Replace: "), "cyan", attrs=["bold"])

# Ask Kext Location
kextLocation = colored(input("Please Enter The Kext Location: "), "cyan", attrs=["bold"])

# Script run dir
scriptDir = os.path.dirname(os.path.realpath(__file__))

# Print Confirmation
successPrint(f"Kext Replaced Directory: {kextDir}")
successPrint(f"Kext Location: {kextLocation}")

# Checking Secure Boot status
if runShellCommand("nvram 94b73556-2197-4702-82a8-3e1337dafbfb:AppleSecureBootPolicy").stdout.decode().split("%")[1].strip() == '00':
    successPrint("Apple Secure Boot is Disabled! Proceeding...")
else:
    warningPrint("Apple Secure Boot is enabled! It has to be turned off in order to continue.")
    warningPrint("Please set SecureBootModel to Disabled.")
    sys.exit()

# Checking SIP status
if (py_sip_xnu.SipXnu().get_sip_status().can_edit_root and py_sip_xnu.SipXnu().get_sip_status().can_load_arbitrary_kexts):
    successPrint("Compatible SIP value detected! Proceeding...")
else:
    warningPrint("Your SIP value is too low! It needs to be at least 0x803.")
    warningPrint("That means csr-active-config has to be set to at least 03080000.")
    warningPrint("If this has already been done, you might also need to reset NVRAM.")
    sys.exit()

choice = input("The script is ready to start. Type \"I am sure that I want to downgrade my root volume\" if you're sure you want to proceed: ")
if choice == "I am sure that I want to downgrade my root volume":
    print("Proceeding with replacing kexts.")
else:
    print("Exiting...")
    sys.exit()

# Backing up original kexts
if not os.path.exists(f"{scriptDir}/Backups"):
    os.mkdir(f"{scriptDir}/Backups")

# Get Kext Name
kextName = os.path.basename(kextDir)

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
cpResult = runShellCommand(f"sudo cp -Rf {kextLocation} {kextDir}")
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
    print("Failed to rebuild KC!")
    print(resultKC.stdout.decode())
    print("")
    sys.exit()
print("Successfully rebuilt KC!")

# Create system volume snapshot
resultBless = runShellCommand("sudo bless --folder /System/Volumes/Update/mnt1/System/Library/CoreServices --bootefi --create-snapshot")
if resultBless.returncode != 0:
    print("Failed to create system volume snapshot!!")
    print(resultBless.stdout.decode())
    print("")
    sys.exit()
print("Successfully created a new APFS volume snapshot!")

print("Successfully replaced the required kexts!")
sys.exit(0)