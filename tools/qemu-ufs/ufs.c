/*
 * PCI + UFSHCI bring-up for QEMU's "ufs" device on -M virt,highmem-ecam=off:
 * assign BAR0, enable the host controller, DME_LINKSTARTUP, then start the
 * UTP transfer request list on a scratch list the way ABL leaves the phone.
 * bsd/dev/sweet_ufs.c takes over from there (it re-points UTRLBA).
 */
#include <stdint.h>

#define ECAM		0x3f000000UL	/* virt VIRT_PCIE_ECAM (low) */
#define UFS_DEVFN	(5u << 3)	/* -device ufs,addr=05.0 */
#define UFS_BAR		0x10000000UL	/* start of the 32-bit PCI MMIO window */

#define REG_HCS		0x30
#define REG_HCE		0x34
#define REG_IS		0x20
#define REG_UTRLBA	0x50
#define REG_UTRLBAU	0x54
#define REG_UTRLRSR	0x60
#define REG_UICCMD	0x90
#define HCS_DP		(1u << 0)
#define HCS_UTRLRDY	(1u << 1)
#define HCS_UCRDY	(1u << 3)
#define IS_UCCS		(1u << 10)
#define UIC_DME_LINKSTARTUP	0x16

static uint8_t utrl[32 * 32] __attribute__((aligned(1024)));

/*
 * Plain ldr/str only: under HVF an MMIO abort is emulated from the ESR's
 * syndrome, which writeback or pair forms do not provide (QEMU asserts isv).
 */
static inline uint32_t rd(uintptr_t a)
{
	uint32_t v;
	__asm__ volatile("ldr %w0, [%1]" : "=r"(v) : "r"(a) : "memory");
	return v;
}

static inline void wr(uintptr_t a, uint32_t v)
{
	__asm__ volatile("str %w0, [%1]" : : "r"(v), "r"(a) : "memory");
}

static void spin(uintptr_t a, uint32_t mask, uint32_t want)
{
	for (unsigned i = 0; i < 10000000 && (rd(a) & mask) != want; i++)
		;
}

void qemu_ufs_init(void)
{
	uintptr_t cfg = ECAM + ((uintptr_t)UFS_DEVFN << 12);

	if ((rd(cfg) & 0xffff) == 0xffff)
		return;				/* no ufs device: nothing to do */
	wr(cfg + 0x10, UFS_BAR | 4);		/* BAR0, 64-bit memory */
	wr(cfg + 0x14, 0);
	wr(cfg + 0x04, rd(cfg + 0x04) | 0x6);	/* memory space + bus master */

	wr(UFS_BAR + REG_HCE, 1);
	spin(UFS_BAR + REG_HCE, 1, 1);
	spin(UFS_BAR + REG_HCS, HCS_UCRDY, HCS_UCRDY);
	wr(UFS_BAR + REG_UICCMD, UIC_DME_LINKSTARTUP);
	spin(UFS_BAR + REG_IS, IS_UCCS, IS_UCCS);
	wr(UFS_BAR + REG_IS, rd(UFS_BAR + REG_IS));
	spin(UFS_BAR + REG_HCS, HCS_DP | HCS_UTRLRDY, HCS_DP | HCS_UTRLRDY);

	wr(UFS_BAR + REG_UTRLBA, (uint32_t)(uintptr_t)utrl);
	wr(UFS_BAR + REG_UTRLBAU, 0);
	wr(UFS_BAR + REG_UTRLRSR, 1);
}
