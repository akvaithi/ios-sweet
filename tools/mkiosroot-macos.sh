#!/bin/bash
# macOS port of mkiosroot.sh + sweet-root-tweaks.py: build the iOS root as one
# case-sensitive journaled HFS+ volume (raw, no partition map) for barbet's
# userdata partition (rd=ufsroot0).
#
#   sudo mkiosroot-macos.sh IPSW OUT_DIR [SIZE]        (SIZE default 16g)
#
# macOS mounts the IPSW's APFS images natively (no apfs-fuse) and creates
# HFS+ itself (no hfsprogs). Files are copied through the VFS, so the
# LZBITMAP-compressed APFS files land uncompressed, as in the Linux build.
# Output: OUT_DIR/ios16-root.img (raw HFS+), flash with
#   fastboot -S 512M flash userdata OUT_DIR/ios16-root.img
set -euo pipefail

[[ $EUID == 0 ]] || { echo "run with sudo (files must keep their iOS owners)" >&2; exit 1; }
[[ $# -ge 2 ]] || { sed -n '2,12p' "$0"; exit 2; }
mkdir -p "$2"
ipsw=$1 outdir=$(realpath "$2") size=${3:-16g}
tools=$(cd "$(dirname "$0")" && pwd)
RSYNC=/opt/homebrew/bin/rsync	# GNU rsync 3: hard links (-H); macOS openrsync is not trusted for that
[[ -x $RSYNC ]] || RSYNC=rsync
OS=087-86698-044.dmg SYSOS=087-86593-047.dmg APPOS=087-86715-047.dmg	# 20H392, NOTES.md
out=$outdir/ios16-root.img
[[ ! -e $out ]] || { echo "refusing to overwrite $out" >&2; exit 1; }

work=$outdir/work
mkdir -p "$work"
mounts=()
cleanup() {
	for m in ${mounts[@]+"${mounts[@]}"}; do hdiutil detach -force "$m" >/dev/null 2>&1 || true; done
}
trap cleanup EXIT

if [[ -f $work/$OS && -f $work/$SYSOS && -f $work/$APPOS ]]; then
	echo "reusing extracted images in $work"
else
	echo "extracting OS, SystemOS and AppOS images"
	unzip -o -q "$ipsw" "$OS" "$SYSOS" "$APPOS" -d "$work"
fi

attach() {	# image mountpoint [raw]
	mkdir -p "$2"
	local key=()
	[[ ${3:-} == raw ]] && key=(-imagekey diskimage-class=CRawDiskImage)
	hdiutil attach -readonly -nobrowse -owners on ${key[@]+"${key[@]}"} -mountpoint "$2" "$1" >/dev/null
	mounts+=("$2")
}
attach "$work/$OS" "$work/os"
attach "$work/$SYSOS" "$work/sysos" raw
attach "$work/$APPOS" "$work/appos" raw

echo "creating $size case-sensitive journaled HFS+ volume"
hdiutil create -size "$size" -layout NONE -fs "Case-sensitive Journaled HFS+" \
	-volname iOSRoot -type SPARSE "$work/root.sparseimage" >/dev/null
mkdir -p "$work/root"
hdiutil attach -nobrowse -owners on -mountpoint "$work/root" "$work/root.sparseimage" >/dev/null
mounts=("$work/root" ${mounts[@]+"${mounts[@]}"})
R=$work/root

copy() {
	echo "copying $1 -> ${2#"$R"}"
	mkdir -p "$2"
	"$RSYNC" -aH --numeric-ids "$1/" "$2/"
}
copy "$work/os" "$R"
copy "$work/sysos" "$R/private/preboot/Cryptexes/OS"
copy "$work/appos" "$R/private/preboot/Cryptexes/App"

# Shared cache where dyld looks at ignition level 1 (hard links).
dsc=private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld
mkdir -p "$R/System/Library/Caches/com.apple.dyld"
for f in "$R/$dsc"/*; do ln "$f" "$R/System/Library/Caches/com.apple.dyld/${f##*/}"; done

# Cryptex files with no counterpart in the OS root, linked to their root path.
for c in OS App; do
	(cd "$R/private/preboot/Cryptexes/$c" && find . ! -type d ! -path './System/Library/Caches/com.apple.dyld/*') |
	while IFS= read -r f; do
		f=${f#./}
		if [[ ! -e $R/$f && ! -L $R/$f ]]; then
			mkdir -p "$R/$(dirname "$f")"
			src=$R/private/preboot/Cryptexes/$c/$f
			if [[ -L $src ]]; then cp -P "$src" "$R/$f"; else ln "$src" "$R/$f"; fi
		fi
	done
done

# logd stores (owner _logd 272, .migrated markers).
db=$R/private/var/db
install -d -o 272 -g 272 -m 0751 "$db/diagnostics"
install -d -o 272 -g 272 -m 0755 "$db/uuidtext" "$db/diagnostics/timesync"
for d in diagnostics uuidtext diagnostics/timesync; do
	install -o 272 -g 272 -m 0644 /dev/null "$db/$d/.migrated"
done

# System keybag for the built-in AppleKeyStore (no passcode).
install -d -m 0700 -o 0 -g 0 "$R/private/var/keybags"
printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' \
	'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
	'<plist version="1.0"><dict><key>KeyBagKeys</key><data>U1dFRVQ=</data></dict></plist>' \
	> "$R/private/var/keybags/systembag.kb"
chown 0:0 "$R/private/var/keybags/systembag.kb"
chmod 0600 "$R/private/var/keybags/systembag.kb"

# The bring-up changes that took sweet to the home screen (launchd, Setup,
# activation, migration, audio, ...).
python3 -I "$tools/sweet-root-tweaks.py" "$R"

df -h "$R"
for m in ${mounts[@]+"${mounts[@]}"}; do hdiutil detach "$m" >/dev/null; done
mounts=()
rm -f "$work/$OS" "$work/$SYSOS" "$work/$APPOS"

echo "converting to a raw volume image"
hdiutil convert "$work/root.sparseimage" -format UDTO -o "$work/root" >/dev/null
mv "$work/root.cdr" "$out"
rm -f "$work/root.sparseimage"
dev=$(hdiutil attach -nomount -imagekey diskimage-class=CRawDiskImage "$out" | awk 'NR==1{print $1}')
fsck_hfs -fn "$dev" || true
hdiutil detach "$dev" >/dev/null
chown "${SUDO_UID:-0}:${SUDO_GID:-0}" "$out"
shasum -a 256 "$out" | tee "$out.sha256"
ls -l "$out"
