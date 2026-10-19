/* Host test of shim/loader.c find_payload(): payload behind an unaligned prefix. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
void con_hex2(const char *l, const char *a, uint32_t va, const char *b, uint32_t vb) { printf("%s %s%x %s%x\n", l, a, va, b ? b : "", vb); }
void con_hex(const char *l, uint64_t v) { printf("%s %llx\n", l, (unsigned long long)v); }
void con_str(const char *l, const char *s) { printf("%s %s\n", l, s); }
#define static
#define loader_boot loader_boot_unused
#include "loader.c"
#undef static
int fdt_chosen_u64(uintptr_t f, const char *p, uint64_t *o) { return 0; }
int main(int argc, char **argv)
{
	FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f);
	for (int pre = 0; pre < 9; pre++) {
		size_t prefix = 30355171 % 4096 + pre;	/* odd, like barbet's vendor ramdisk */
		uint8_t *buf = aligned_alloc(4096, (prefix + n + 4095) / 4096 * 4096);
		memset(buf, 0x5a, prefix);
		rewind(f); fread(buf + prefix, 1, n, f);
		uint8_t *ref = malloc(n); rewind(f); fread(ref, 1, n, f);
		uintptr_t got = find_payload((uintptr_t)buf, (uintptr_t)buf + prefix + n);
		int ok = got == (uintptr_t)buf && !memcmp(buf, ref, n);
		printf("prefix %zu: %s got_off=%ld\n", prefix, ok ? "OK" : "FAIL", (long)(got - (uintptr_t)buf));
		if (!ok) { long i = 0; while (i < n && buf[i] == ref[i]) i++; printf("first diff at %ld of %ld\n", i, n); }
		if (!ok) return 1;
		free(buf); free(ref);
	}
	return 0;
}
