# GPG-Encrypted Key Containers Implementation Plan

## Overview

This document outlines the implementation plan for creating GPG-encrypted disk and archive containers in nixos-secrets, which will be decrypted during initrd boot using a YubiKey.

## Current Architecture

### nixos-keys
- Creates SquashFS disk images or tar.gz archives containing SSH keys
- Currently **unencrypted**
- Script: `scripts/create.nix`

### nixos-config
- Loads keys during initrd (stage 1) from SquashFS devices
- Module: `hosts/iso/load-keys.nix`
- Supports both Ventoy injection and QEMU disk attachment

### nixos-secrets
- Uses SOPS with age + PGP for encrypting secrets
- PGP key configured: `82D7B6F3AF8297688F10508CB692AA74EC31CD0B`
- Configuration: `.sops.yaml`

## Requirements

### Security Requirements
- Encrypt key containers using GPG with YubiKey
- YubiKey requires **both PIN and touch** for operations
- Decrypt containers during initrd boot stage

### Operational Requirements
- **Graceful fallback**: Boot continues without keys if YubiKey not present
- Support **both** formats: SquashFS disk and tar.gz archive
- Store encrypted containers in nixos-secrets repo root
- Provide cleanup command to remove encrypted containers

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CREATE PHASE (nixos-secrets)             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  nixos-keys/          SquashFS/tar.gz        GPG encrypt    │
│  keys/ ────────────> (temp directory) ────────────────────> │
│                                                             │
│                      Output: <hostname>-keys.img.gpg        │
│                              <hostname>-keys.tar.gz.gpg     │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                 BOOT PHASE (nixos-config initrd)            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  YubiKey ──> gpg-agent ──> decrypt ──> mount ──> load keys │
│  (PIN+touch) (scdaemon)    (to tmpfs)  SquashFS            │
│                                                             │
│  If YubiKey not present or fails:                          │
│  ──> Log warning ──> Continue boot without keys            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Tasks

### Phase 1: nixos-secrets Repository

#### 1.1 Create Documentation Directory
- [x] Create `docs/` directory
- [x] Create this plan document

#### 1.2 Add Encryption Commands to shell.nix

**New commands to add:**

```nix
{
  category = "encryption";
  name = "create-encrypted-disk";
  help = "Create GPG-encrypted SquashFS disk for a host";
  command = ''
    if [ -z "${1:-}" ]; then
      echo "Usage: create-encrypted-disk <hostname>"
      echo "Example: create-encrypted-disk nanoserver"
      exit 1
    fi
    
    HOSTNAME="$1"
    
    # Verify nixos-keys repo is available
    if [ ! -d "../nixos-keys" ]; then
      echo "Error: nixos-keys repository not found"
      echo "Expected: ../nixos-keys"
      exit 1
    fi
    
    # Run the encryption script
    ${pkgs.bash}/bin/bash scripts/create-encrypted.sh disk "$HOSTNAME"
  '';
}

{
  category = "encryption";
  name = "create-encrypted-archive";
  help = "Create GPG-encrypted tar.gz archive for a host";
  command = ''
    if [ -z "${1:-}" ]; then
      echo "Usage: create-encrypted-archive <hostname>"
      echo "Example: create-encrypted-archive nanoserver"
      exit 1
    fi
    
    HOSTNAME="$1"
    ${pkgs.bash}/bin/bash scripts/create-encrypted.sh archive "$HOSTNAME"
  '';
}

{
  category = "encryption";
  name = "cleanup-encrypted";
  help = "Remove encrypted containers from repo root";
  command = ''
    echo "Cleaning up encrypted containers..."
    rm -vf ./*.img.gpg ./*.tar.gz.gpg
    echo "Done"
  '';
}
```

**Required packages to add to shell.nix:**
```nix
packages = with pkgs; [
  # Existing packages...
  sops
  age
  ssh-to-age
  mkpasswd
  gnupg
  git
  
  # Add for encryption
  squashfsTools
  gnutar
  gzip
];
```

#### 1.3 Create Encryption Script

**File: `scripts/create-encrypted.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

FORMAT="$1"
HOSTNAME="$2"
GPG_KEY="82D7B6F3AF8297688F10508CB692AA74EC31CD0B"
KEYS_REPO="../nixos-keys"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info() { echo -e "${CYAN}$*${NC}"; }
success() { echo -e "${GREEN}$*${NC}"; }
error() { echo -e "${RED}$*${NC}" >&2; }

# Verify host exists
if [ ! -d "$KEYS_REPO/hosts/$HOSTNAME" ]; then
  error "Error: Host not found in nixos-keys: $HOSTNAME"
  exit 1
fi

# Create temporary directory
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

info "Creating unencrypted $FORMAT for $HOSTNAME..."

# Copy SSH host keys
if [ -f "$KEYS_REPO/hosts/$HOSTNAME/ssh_host_ed25519_key" ]; then
  info "Copying SSH host keys..."
  mkdir -p "$TEMP_DIR/etc/ssh"
  cp "$KEYS_REPO/hosts/$HOSTNAME"/ssh_host_* "$TEMP_DIR/etc/ssh/"
fi

# Copy deploy keys
if [ -f "$KEYS_REPO/hosts/$HOSTNAME/deploy_key_ed25519" ]; then
  info "Copying deploy keys..."
  mkdir -p "$TEMP_DIR/root/.ssh"
  cp "$KEYS_REPO/hosts/$HOSTNAME"/deploy_key_* "$TEMP_DIR/root/.ssh/"
fi

# Copy user keys (if available)
if [ -d "$KEYS_REPO/home" ]; then
  info "Copying user keys..."
  for user_dir in "$KEYS_REPO/home"/*; do
    if [ -d "$user_dir" ]; then
      user=$(basename "$user_dir")
      mkdir -p "$TEMP_DIR/home/$user/.ssh"
      cp "$user_dir"/* "$TEMP_DIR/home/$user/.ssh/" 2>/dev/null || true
    fi
  done
fi

# Create container based on format
case "$FORMAT" in
  disk)
    UNENCRYPTED="$TEMP_DIR/$HOSTNAME-keys.img"
    OUTPUT="$HOSTNAME-keys.img.gpg"
    
    info "Creating SquashFS image..."
    mksquashfs "$TEMP_DIR" "$UNENCRYPTED" -quiet -noappend -comp xz
    ;;
    
  archive)
    UNENCRYPTED="$TEMP_DIR/$HOSTNAME-keys.tar.gz"
    OUTPUT="$HOSTNAME-keys.tar.gz.gpg"
    
    info "Creating tar.gz archive..."
    (cd "$TEMP_DIR" && tar czf "$UNENCRYPTED" ./*)
    ;;
    
  *)
    error "Unknown format: $FORMAT"
    exit 1
    ;;
esac

# Encrypt with GPG
info "Encrypting with GPG (YubiKey PIN + touch required)..."
gpg --encrypt --recipient "$GPG_KEY" --output "$OUTPUT" "$UNENCRYPTED"

# Verify output
if [ -f "$OUTPUT" ]; then
  SIZE=$(du -h "$OUTPUT" | cut -f1)
  success "✓ Encrypted container created: $OUTPUT"
  echo "  Host: $HOSTNAME"
  echo "  Format: $FORMAT"
  echo "  Size: $SIZE"
  echo "  Encrypted with: $GPG_KEY"
else
  error "Error: Failed to create encrypted container"
  exit 1
fi
```

### Phase 2: nixos-config Repository

#### 2.1 Update hosts/iso/load-keys.nix

**Add kernel modules for USB/YubiKey:**

```nix
boot.initrd = {
  # Existing modules
  kernelModules = [
    "squashfs"
    "virtio_blk"
    "virtio_pci"
    
    # USB support for YubiKey
    "usb_storage"
    "usbhid"
    "ehci_pci"
    "xhci_pci"
    "uhci_hcd"
    
    # Smartcard support
    "ccid"
  ];
  
  availableKernelModules = [
    "squashfs"
    "virtio_blk"
    "virtio_pci"
    "usb_storage"
    "usbhid"
  ];
};
```

**Add GPG tools to initrd:**

```nix
boot.initrd = {
  extraUtilsCommands = ''
    # Existing commands
    copy_bin_and_libs ${pkgs.load-keys}/bin/load-keys
    copy_bin_and_libs ${pkgs.util-linux}/bin/blkid
    
    # GPG tools for decryption
    copy_bin_and_libs ${pkgs.gnupg}/bin/gpg
    copy_bin_and_libs ${pkgs.gnupg}/bin/gpg-agent
    copy_bin_and_libs ${pkgs.gnupg}/libexec/scdaemon
    copy_bin_and_libs ${pkgs.pinentry-curses}/bin/pinentry-curses
    
    # Required for GPG
    mkdir -p $out/etc/gnupg
    cat > $out/etc/gnupg/gpg-agent.conf <<EOF
pinentry-program ${pkgs.pinentry-curses}/bin/pinentry-curses
enable-ssh-support
EOF
  '';
};
```

**Update postMountCommands for encrypted containers:**

```nix
boot.initrd.postMountCommands = ''
  echo "=== Stage 1: Loading SSH keys ==="
  
  # Function to decrypt GPG container
  decrypt_container() {
    local encrypted_file="$1"
    local decrypted_file="$2"
    
    echo "Attempting to decrypt: $encrypted_file"
    
    # Start GPG agent
    export GPG_TTY=/dev/console
    export GNUPGHOME=/tmp/gnupg
    mkdir -p "$GNUPGHOME"
    chmod 700 "$GNUPGHOME"
    
    # Try to decrypt (will prompt for PIN + require touch)
    if gpg --decrypt --output "$decrypted_file" "$encrypted_file" 2>/dev/null; then
      echo "✓ Decryption successful"
      return 0
    else
      echo "⚠ Warning: Decryption failed (YubiKey not present or incorrect PIN)"
      return 1
    fi
  }
  
  # Method 1: Check for Ventoy-injected keys
  if [ -d /etc/ssh ] || [ -d /root/.ssh ] || [ -d /home ]; then
    echo "Found Ventoy-injected keys, copying to target..."
    ${pkgs.load-keys}/bin/load-keys / $targetRoot
  fi
  
  # Method 2: Check for QEMU SquashFS disk
  echo "Scanning for keys disk..."
  KEYS_DEV=""
  
  for dev in /dev/vd[a-z] /dev/sd[a-z] /dev/hd[a-z]; do
    if [ -b "$dev" ]; then
      FS_TYPE=$(blkid -s TYPE -o value "$dev" 2>/dev/null || echo "")
      
      # Check for encrypted GPG file or SquashFS
      if [ "$FS_TYPE" = "squashfs" ]; then
        echo "Found SquashFS device: $dev"
        KEYS_DEV="$dev"
        break
      fi
    fi
  done
  
  if [ -n "$KEYS_DEV" ]; then
    echo "Attempting to load keys from $KEYS_DEV..."
    mkdir -p /mnt-keys
    
    if mount -t squashfs -o ro "$KEYS_DEV" /mnt-keys 2>/dev/null; then
      echo "✓ Mounted SquashFS keys disk"
      
      # Check if it's encrypted (contains .gpg files)
      if ls /mnt-keys/*.gpg 2>/dev/null; then
        echo "Detected encrypted container"
        DECRYPTED_DIR=$(mktemp -d)
        
        for gpg_file in /mnt-keys/*.gpg; do
          BASENAME=$(basename "$gpg_file" .gpg)
          DECRYPTED_FILE="$DECRYPTED_DIR/$BASENAME"
          
          if decrypt_container "$gpg_file" "$DECRYPTED_FILE"; then
            # Mount decrypted SquashFS
            mkdir -p /mnt-decrypted
            if mount -t squashfs -o ro,loop "$DECRYPTED_FILE" /mnt-decrypted; then
              ${pkgs.load-keys}/bin/load-keys /mnt-decrypted $targetRoot
              umount /mnt-decrypted
              rmdir /mnt-decrypted
            fi
            
            # Securely wipe decrypted file
            dd if=/dev/zero of="$DECRYPTED_FILE" bs=1M 2>/dev/null || true
            rm -f "$DECRYPTED_FILE"
          else
            echo "⚠ Warning: Continuing boot without encrypted keys"
          fi
        done
        
        rm -rf "$DECRYPTED_DIR"
      else
        # Unencrypted SquashFS
        ${pkgs.load-keys}/bin/load-keys /mnt-keys $targetRoot
      fi
      
      umount /mnt-keys
      rmdir /mnt-keys
    else
      echo "⚠ Warning: Found SquashFS device but failed to mount"
    fi
  else
    echo "No keys disk found (checked /dev/vd[a-z], /dev/sd[a-z], /dev/hd[a-z])"
  fi
  
  echo "=== Stage 1: Key loading complete ==="
'';
```

## Testing Workflow

### Create Encrypted Container

```bash
# In nixos-secrets repo
cd nixos-secrets
nix develop

# Create encrypted disk (requires YubiKey)
create-encrypted-disk nanoserver
# Output: nanoserver-keys.img.gpg

# Create encrypted archive
create-encrypted-archive nanoserver
# Output: nanoserver-keys.tar.gz.gpg

# Cleanup when done
cleanup-encrypted
```

### Test with QEMU

```bash
# In nixos-config repo
cd nixos-config
nix develop

# Build and run ISO with encrypted keys disk
iso run -k ../nixos-secrets/nanoserver-keys.img.gpg

# During boot:
# 1. YubiKey will be detected
# 2. PIN prompt will appear
# 3. Touch YubiKey when LED blinks
# 4. Keys will be decrypted and loaded
```

### Test Fallback (No YubiKey)

```bash
# Remove YubiKey before boot
iso run -k ../nixos-secrets/nanoserver-keys.img.gpg

# Expected behavior:
# - Decryption fails gracefully
# - Warning logged to serial console
# - Boot continues without keys
# - System accessible but secrets unavailable
```

## Security Considerations

### Encryption
- GPG key: `82D7B6F3AF8297688F10508CB692AA74EC31CD0B`
- YubiKey required for decryption
- Both PIN and touch required
- Private key never leaves YubiKey

### Decryption
- Happens in initrd (early boot)
- Decrypted data stored in tmpfs (RAM)
- Securely wiped after use
- No persistent decrypted copies

### Fallback
- Graceful degradation when YubiKey absent
- Boot continues without keys
- Logged warnings visible in serial console
- Prevents total system lockout

## Files Modified/Created

### nixos-secrets
- `docs/GPG-ENCRYPTED-KEYS.md` (this file)
- `shell.nix` - Add encryption commands
- `scripts/create-encrypted.sh` - Encryption script

### nixos-config
- `hosts/iso/load-keys.nix` - GPG/YubiKey initrd support

## References

- SOPS: https://github.com/mozilla/sops
- GnuPG: https://gnupg.org/
- YubiKey GPG: https://support.yubico.com/hc/en-us/articles/360013790259-Using-Your-YubiKey-with-OpenPGP
- NixOS initrd: https://nixos.org/manual/nixos/stable/options.html#opt-boot.initrd

## Task Checklist

### Phase 1: nixos-secrets
- [x] Create documentation directory
- [x] Create implementation plan (this document)
- [ ] Add encryption commands to shell.nix
- [ ] Create scripts/create-encrypted.sh
- [ ] Add required packages to shell.nix
- [ ] Test encrypted disk creation
- [ ] Test encrypted archive creation

### Phase 2: nixos-config
- [ ] Add USB/smartcard kernel modules to initrd
- [ ] Add GPG tools to initrd extraUtilsCommands
- [ ] Update postMountCommands for encrypted container detection
- [ ] Implement graceful fallback on decryption failure
- [ ] Test QEMU boot with encrypted disk
- [ ] Test fallback without YubiKey

### Phase 3: Documentation
- [ ] Update README.md in nixos-secrets
- [ ] Add usage examples
- [ ] Document troubleshooting steps
