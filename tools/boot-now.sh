#!/bin/bash
# Build a barbet boot image with the current time and RAM-boot it.
#   tools/boot-now.sh KERNEL [extra boot-args...]
# The kernel has no usable RTC (xnu 0093): sweettime=<unix secs> stamped
# here is the wall clock iOS starts from, so build right before booting.
# Uses shim/out/barbet.adt (tools/mkadt.py shim/out/barbet.adt --highmem).
set -euo pipefail
cd "$(dirname "$0")/.."
kernel=$1; shift
args="debug=0xc serial=3 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin launchd_unsecure_cache=1 wdt=-1 sweetfb_hz=30 sweetusb=0 sweetfb_noconsole=1 cpus=1 ufsrw=1 rootrw=1 sweetlog=1 sweetkeys=1 sweettouch=1 sweetswipe=0"
for a in "$@"; do	# key=value overrides; key=- removes key
	args=$(printf '%s\n' $args | grep -v "^${a%%=*}=" | tr '\n' ' ')
	[[ $a == *=- ]] || args="$args$a"
done
args="$args sweettime=$(date +%s)"
python3 tools/mkpayload.py "$kernel" shim/out/barbet.adt shim/out/payload-now.bin --cmdline "$args" >/dev/null
(cd shim && ./build.sh ../shim/out/payload-now.bin >/dev/null 2>&1 && cp out/shim-boot.img out/shim-boot-now.img)
echo "boot-args: $args"
fastboot boot shim/out/shim-boot-now.img
