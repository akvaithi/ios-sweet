/*
 * Host test of bsd/dev/sweet_touchcore.c (xnu patch 0100). From a patched tree:
 *   cc -I bsd/dev -o /tmp/stc_test sweet_touchcore_test.c bsd/dev/sweet_touchcore.c -lm && /tmp/stc_test
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "sweet_touchcore.h"
#define R 36
#define C 16
static struct stc_core core;
static int16_t f[R*C];
static void frame(double fr, double fc, double amp, double sig, int noise_seed) {
	srand(noise_seed);
	for (int r = 0; r < R; r++) for (int c = 0; c < C; c++) {
		double d = (r-fr)*(r-fr) + (c-fc)*(c-fc);
		int v = 1000 + (rand()%21 - 10);
		if (amp > 0) v += (int)(amp*exp(-d/(2*sig*sig)));
		f[r*C+c] = v;
	}
}
static int fails;
#define CHECK(c, ...) do { if (!(c)) { printf("FAIL: " __VA_ARGS__); printf("\n"); fails++; } } while (0)
int main(void) {
	struct stc_config cfg = {R, C, 1080, 2400, 0, 0, 0, 60, 200, 120, 40, 300};
	struct stc_contact out[STC_SLOTS];
	stc_reset(&core);
	for (int i = 0; i < STC_STARTUP; i++) { frame(0,0,0,1,i); CHECK(stc_process(&core,&cfg,f,out,STC_SLOTS) == -1, "startup %d", i); }
	frame(0,0,0,1,99); CHECK(stc_process(&core,&cfg,f,out,STC_SLOTS) == 0, "quiet frame reports nothing");
	/* finger at node (18, 8): expect ~ x=(8.5/16)*1080=573, y=(18.5/36)*2400=1233 */
	frame(18,8,600,1.0,1); int n = stc_process(&core,&cfg,f,out,STC_SLOTS);
	CHECK(n == 0, "first frame of a slot is not reported (got %d)", n);
	frame(18,8,600,1.0,2); n = stc_process(&core,&cfg,f,out,STC_SLOTS);
	CHECK(n == 1, "second frame reports one contact (got %d)", n);
	if (n == 1) { printf("contact slot=%d x=%d y=%d peak=%d area=%d\n", out[0].slot,out[0].x,out[0].y,out[0].peak,out[0].area);
		CHECK(abs(out[0].x-573) < 40 && abs(out[0].y-1233) < 40, "centroid near (573,1233)"); }
	/* move one node down: same slot */
	int slot0 = n ? out[0].slot : -1;
	frame(19,8,600,1.0,3); n = stc_process(&core,&cfg,f,out,STC_SLOTS);
	CHECK(n == 1 && out[0].slot == slot0 && out[0].y > 1233, "tracked move keeps slot, y grows");
	/* lift */
	frame(0,0,0,1,4); n = stc_process(&core,&cfg,f,out,STC_SLOTS); CHECK(n == 0, "lift reports nothing");
	/* weak bump below down threshold never starts */
	frame(5,5,150,1.0,5); stc_process(&core,&cfg,f,out,STC_SLOTS); frame(5,5,150,1.0,6);
	n = stc_process(&core,&cfg,f,out,STC_SLOTS); CHECK(n == 0, "sub-threshold bump ignored");
	/* palm: huge blob rejected */
	frame(18,8,800,6.0,7); stc_process(&core,&cfg,f,out,STC_SLOTS); frame(18,8,800,6.0,8);
	n = stc_process(&core,&cfg,f,out,STC_SLOTS); CHECK(n == 0, "palm rejected (got %d)", n);
	/* two fingers */
	frame(0,0,0,1,9); stc_process(&core,&cfg,f,out,STC_SLOTS);
	for (int k = 0; k < 2; k++) {
		frame(6,3,600,1.0,10+k); for (int i=0;i<R*C;i++) { int r=i/C,c=i%C; double d=(r-30)*(r-30)+(c-12)*(c-12); f[i]+= (int)(600*exp(-d/2)); }
		n = stc_process(&core,&cfg,f,out,STC_SLOTS);
	}
	CHECK(n == 2, "two fingers (got %d)", n);
	/* orientation flags */
	struct stc_config c2 = cfg; c2.flip_x = 1; c2.flip_y = 1; stc_reset(&core);
	for (int i = 0; i < STC_STARTUP; i++) { frame(0,0,0,1,i); stc_process(&core,&c2,f,out,STC_SLOTS); }
	frame(2,2,600,1.0,1); stc_process(&core,&c2,f,out,STC_SLOTS); frame(2,2,600,1.0,2);
	n = stc_process(&core,&c2,f,out,STC_SLOTS);
	CHECK(n == 1 && out[0].x > 900 && out[0].y > 2100, "flip_x/flip_y map a top-left node to bottom-right");
	printf("%s (%d failures)\n", fails ? "FAILED" : "all passed", fails);
	return fails != 0;
}
