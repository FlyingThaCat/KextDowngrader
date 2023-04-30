# Kext Downgrader
This script automates the whole process of downgrading kext. And it automatically backup the original kext 

## Prerequisites

To use this script, you need to partially disable SIP: csr-active-config -> 03080000 or higher, and Apple Secure Boot: SecureBootModel -> Disabled.
This will weaken macOS' security by a little bit. It will enable installing unsigned kext extensions and modifying the file system of macOS.
You will also not be able to download any delta OTA updates, so when you want to update macOS, you will need to download the full 12GB update.
It is up to each person to decide if this compromise is worth it.

You will need the `-i` args for input kexts
And Just Restore it with `-r`

# Credits

Apple for macOS
ExtremeXT for APUDowngrader
Dortania for OpenCore Legacy Patcher
