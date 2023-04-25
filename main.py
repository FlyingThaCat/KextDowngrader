import platform
import sys
import subprocess
import plistlib
import os
import logging

try:
    import py_sip_xnu
except:
    logging.error("Could not import py_sip_xnu! Please run pip3 install py_sip_xnu.")
    sys.exit(-1)

# Thanks to OCLP for some of the code
# https://github.com/dortania/OpenCore-Legacy-Patcher/blob/main/resources/sys_patch/sys_patch.py

# TODO: Tidy up the error codes
# Error code -1 = files not detected
# Error code 0 = success
# Error code 1 = unsupported OS
# Error code 2 = insufficient SIP value
# Error code 3 = failed to rebuild KC
# Error code 4 = failed to create snapshot

# TODO: Add Ventura support
mac_version = str(platform.mac_ver()[0].split('.')[0])
if mac_version < '12':
    logging.error(f"macOS version {mac_version} is not supported!")
    sys.exit(1)
elif mac_version == '12':
    logging.info(f"macOS Monterey detected! Proceeding...")
elif mac_version == '13':
    logging.error("macOS Ventura is unsupported as of now.")
    sys.exit(1)
else:
    logging.error(f"Unknown macOS version ({mac_version}) detected!")
    sys.exit(1)

# TODO: check for files in subdirs of the script
if os.path.exists("AMDRadeonX5000HWLibs.kext") and os.path.exists("AMDRadeonX6000Framebuffer.kext"):
    X50000HWLibsPath = "AMDRadeonX5000HWLibs.kext"
    X6000FramebufferPath = "AMDRadeonX6000Framebuffer.kext"
else:
    logging.error("AMDRadeonX5000HWLibs.kext and/or AMDRadeonX6000Framebuffer.kext not found in the script directory!")
    logging.error("Because of copyright limitations, these files cannot be shared publicly on the repository.")
    logging.error("This means you need to find the means to get these files either by yourself from a Big Sur installation or downloaded from somewhere else.")
    sys.exit(-1)
    
# TODO: Improve writing
# Checking SIP status
if not (py_sip_xnu.SipXnu().get_sip_status().can_edit_root and py_sip_xnu.SipXnu().get_sip_status().can_load_arbitrary_kexts):
    logging.error("Your SIP value is not sufficiently disabled! It needs to be at least 0x803.")
    logging.error("That means csr-active-config has to be set to at least 03080000.")
    logging.error("If this has already been done, you might also need to reset NVRAM.")
    sys.exit(2)

choice = input("The script is ready to start. Press Y if you're sure you want to proceed.")
if choice != "Y":
    sys.exit(0)

# Get the root volume
root_partition_info = plistlib.loads(subprocess.run("diskutil info -plist /".split(), stdout=subprocess.PIPE).stdout.decode().strip().encode())
root_mount_path = root_partition_info["DeviceIdentifier"]
root_mount_path = root_mount_path[:-2] if root_mount_path.count("s") > 1 else root_mount_path

# Mount the root volume
subprocess.call(f'/sbin/mount_apfs -R /dev/{root_mount_path} /System/Volumes/Update/mnt1')

# rm -rf X5000HWLibs & X6000FB
subprocess.run("sudo rm -rf /System/Volumes/Update/mnt1/System/Library/Extensions/AMDRadeonX5000HWServices.kext/Contents/PlugIns/AMDRadeonX5000HWLibs.kext", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
subprocess.run("sudo rm -rf /System/Volumes/Update/mnt1/System/Library/Extensions/AMDRadeonX6000Framebuffer.kext", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

# cp -R X5000HWLibs & X6000FB
subprocess.run(f"sudo cp -R {X50000HWLibsPath} /System/Volumes/Update/mnt1/System/Library/Extensions/AMDRadeonX5000HWServices.kext/Contents/PlugIns/AMDRadeonX5000HWLibs.kext", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
subprocess.run(f"sudo cp -R {X6000FramebufferPath} /System/Volumes/Update/mnt1/System/Library/Extensions/AMDRadeonX6000Framebuffer.kext", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

# Fix permissions
subprocess.run(f"chmod -Rf 755 /System/Volumes/Update/mnt1/System/Library/Extensions/AMDRadeonX5000HWServices.kext/Contents/PlugIns/AMDRadeonX5000HWLibs.kext", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
subprocess.run(f"chown -Rf root:wheel /System/Volumes/Update/mnt1/System/Library/Extensions/AMDRadeonX5000HWServices.kext/Contents/PlugIns/AMDRadeonX5000HWLibs.kext", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

subprocess.run(f"chmod -Rf 755 /System/Volumes/Update/mnt1/System/Library/Extensions/AMDRadeonX6000Framebuffer.kext", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
subprocess.run(f"chown -Rf root:wheel /System/Volumes/Update/mnt1/System/Library/Extensions/AMDRadeonX6000Framebuffer.kext", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

# Rebuild KC
result = subprocess.run(f"sudo kmutil install --volume-root /System/Volumes/Update/mnt1", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

# kmutil notes:
# - will return 71 on failure to build KCs
# - will return 31 on 'No binaries or codeless kexts were provided'
# - will return -10 if the volume is missing (ie. unmounted by another process)
if result.returncode != 0:
    logging.error("Failed to rebuild KC!")
    logging.error(f"Error code: {result.returncode}")
    print(result.stdout.decode())
    print("")
    sys.exit(3)

# Create system volume snapshot
result = subprocess.run(f"sudo bless --folder /System/Volumes/Update/mnt1/System/Library/CoreServices --bootefi --create-snapshot", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

if result.returncode != 0:
    logging.error("Failed to create system volume snapshot!!")
    logging.error(f"Error code: {result.returncode}")
    print(result.stdout.decode())
    print("")
    sys.exit(4)

logging.info("Successfully replaced the required kexts!")
sys.exit(0)