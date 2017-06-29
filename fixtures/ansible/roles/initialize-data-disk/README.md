ENCRYPTED STORAGE
=================

_Sets up a dm-crypted volume based on the [encrypted_storage Ansible role](https://github.com/elastic/infra/blob/master/ansible/roles/encrypted_storage/README.md) from the infra repo._

This role encrypts with LUKS and mounts a defined block device.  The
target for the role is not to make volumes more secure, as the key is
stored on a file in the root file system, but to generate
CI-slaves with a LUKS encrypted FS (typically `/var/lib/jenkins`) that is
automounted across reboots.

Currently it only supports Ubuntu + RHEL/CentOS Linux distributions.

Role Variables
--------------

### Required

These variables are not set by default, but the encrypted\_storage
role relies on them to configure the block device:

#### <kbd>launch\_encrypted\_device</kbd>

This is the block device that should be used by LUKS. On AWS it could be e.g. `/dev/xvdf`

### Optional

#### <kbd>launch\_encrypted\_storage</kbd>

This should be set to `y` for the role to execute. It defaults to `false`
therefore if unset the role will be skipped.

#### <kbd>default_linux_os_filesystem</kbd>

The filesystem to be used for formatting the LUKS presented block device.

Defaults to `ext4` for all OSes except for RHEL/CentOS >=7 where it's set to `xfs`.

#### <kbd>encrypted\_mount\_point</kbd>

The directory to mount the LUKS block device on.
Defaults to `/var/lib/jenkins`.

#### <kbd>encrypted\_volume\_passphrase</kbd>

The passphrase to be used when formatting `launch_encrypted_device` with LUKS.
Defaults to `elastic123`.

#### <kbd>encrypted\_volume\_passphrase\_file</kbd>

The filename where `encrypted_volume_passphrase` will be stored.
Required for automatic mounting of the encrypted file system after a reboot.

#### <kbd>encrypted\_volume\_name</kbd>

The devicemapper name that LUKS will present the encrypted block
device as (`/dev/mapper/<encrypted_volume_name>`). This is used to
populate the `/etc/fstab` and `/etc/crypttab` entries.
