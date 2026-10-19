#pragma once
/*
 * Board constants. Pixel 5a (barbet, SM7250 "lito"), from the factory
 * vendor_boot DTB + "Barbet MP" dtbo overlay (AP2A.240805.005.S4).
 * The sweet (SM7150) values they replace are noted alongside.
 */
#define BOARD_NAME		"barbet"
#define BOARD_FB_BASE		0xa0000000UL	/* cont_splash_region, sweet 0x9c000000 */
#define BOARD_IMEM_RESTART	0x146ab65cUL	/* msm-imem@146ab000 restart_reason@65c, sweet 0x146aa65c */
#define BOARD_PSHOLD		0x0c264000UL	/* restart@c264000, same as sweet */
#define BOARD_GICD		0x17a00000UL	/* same as sweet */
#define BOARD_GICR		0x17a60000UL	/* same as sweet */
#define BOARD_UFS		0x01d84000UL	/* ufshc@1d84000, same as sweet */
